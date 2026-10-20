import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import (
    User, Position, Order, Trade, OrderEvent, RiskConfig,
    RiskEvent, AuditLog, AutomationConfig, AutomationLog,
    ReconciliationRecord, BrokerConnection, TradingAccount
)
from .security_vault import decrypt_secret
from .market_data import market_service
from .strategies import STRATEGY_REGISTRY
from .risk import validate_trade
from .brokers.manager import broker_manager
from .position_manager import position_manager

class AutomationEngine:
    """
    Production-grade Automated Algorithmic Trading Engine for Indian Equities.
    Handles continuous market watch, strategy evaluation, server-side risk checking,
    automatic BUY execution, dynamic stop-loss/target/strategy exits, position monitoring,
    and broker reconciliation.
    """

    def __init__(self):
        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        self._eval_interval_seconds = 6.0
        self._last_reconciliation_time: Optional[datetime] = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self):
        if self._is_running:
            return
        self._is_running = True
        try:
            loop = asyncio.get_running_loop()
            self._task = loop.create_task(self._run_loop())
        except RuntimeError:
            self._task = None

    def stop(self):
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _run_loop(self):
        while self._is_running:
            try:
                await self.run_evaluation_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[AutomationEngine] Cycle error: {e}")
            await asyncio.sleep(self._eval_interval_seconds)

    async def run_evaluation_cycle(self):
        """
        Executes one complete evaluation cycle across all active users.
        """
        with next(get_db()) as db:
            configs = db.scalars(select(AutomationConfig).where(AutomationConfig.is_running == True)).all()
            for cfg in configs:
                await self._process_user_automation(cfg.user_id, cfg, db)

    async def _process_user_automation(self, user_id: int, cfg: AutomationConfig, db: Session):
        now = datetime.utcnow()

        # 1. Check Global Market Data & Kill Switch
        feed_status = market_service.get_feed_status()
        if feed_status in ["NOT CONFIGURED", "DISCONNECTED"]:
            return

        risk_cfg = db.scalar(select(RiskConfig).where(RiskConfig.user_id == user_id))
        if risk_cfg and risk_cfg.kill_switch_active:
            return

        # 2. Get Broker Adapter
        adapter = self._resolve_user_adapter(user_id, cfg, db)

        # 3. Step A: Monitor Open Positions & Automatic Exits (Stop Loss / Target / Strategy Exit)
        open_positions = db.scalars(select(Position).where(Position.user_id == user_id, Position.status == "OPEN")).all()
        for pos in open_positions:
            await self._monitor_and_exit_position(pos, cfg, adapter, user_id, db)

        # 4. Step B: Evaluate New Strategy Trade Entries
        # Enforce max open positions guard
        if len(open_positions) < cfg.max_open_positions:
            await self._evaluate_entries_for_user(user_id, cfg, adapter, risk_cfg, len(open_positions), db)

        # 5. Step C: Periodic Broker Reconciliation (every ~30s)
        if not self._last_reconciliation_time or (now - self._last_reconciliation_time).total_seconds() > 30:
            self._last_reconciliation_time = now
            await self._reconcile_broker_state(user_id, cfg, adapter, open_positions, db)

    async def _monitor_and_exit_position(self, pos: Position, cfg: AutomationConfig, adapter: Any, user_id: int, db: Session):
        """
        Continuously monitors active position. If Stop Loss, Target, or Strategy Exit condition is met,
        automatically places exit SELL order through the connected broker.
        """
        quote = await market_service.get_quote(pos.symbol)
        if not quote:
            return

        ltp = quote.ltp
        pos.current_price = ltp
        pos.unrealized_pnl = round((ltp - pos.avg_price) * pos.quantity, 2)
        db.commit()

        exit_triggered = False
        exit_reason = ""

        # Condition 0: Evaluate via Position Manager (Adaptive Trailing, Session 15:15 IST, Breakeven Lock, Thesis Exit)
        is_option = any(term in pos.symbol.upper() for term in ["CE", "PE", "NIFTY", "BANKNIFTY"]) or (pos.strategy_code and "STRAT_" in pos.strategy_code)
        if is_option:
            und_sym = "BANKNIFTY" if "BANK" in pos.symbol.upper() else "NIFTY"
            und_candles = await market_service.get_historical_data(und_sym, timeframe="5m", limit=30)
            und_spot = ltp
            und_vwap = ltp
            und_atr = 20.0
            if und_candles and len(und_candles) >= 15:
                import pandas as pd
                from .indicators import compute_all_indicators
                df_u = pd.DataFrame([c.__dict__ for c in und_candles])
                df_u = compute_all_indicators(df_u)
                last_u = df_u.iloc[-1]
                und_spot = float(last_u['close'])
                und_vwap = float(last_u.get('vwap', und_spot))
                und_atr = float(last_u.get('atr14', und_spot * 0.007))

            opt_type = "PE" if "PE" in pos.symbol.upper() else "CE"
            dec = position_manager.evaluate_open_position(
                position_id=pos.id,
                symbol=pos.symbol,
                option_type=opt_type,
                entry_price=pos.avg_price,
                current_opt_price=ltp,
                initial_sl=pos.stop_loss or round(pos.avg_price * 0.80, 2),
                current_sl=pos.stop_loss or round(pos.avg_price * 0.80, 2),
                target_price=pos.target or 0.0,
                trailing_type="ATR_TRAILING",
                highest_price_seen=max(pos.current_price or pos.avg_price, ltp),
                bars_held=5,
                underlying_spot=und_spot,
                underlying_vwap=und_vwap,
                regime_15m="BULL" if und_spot >= und_vwap else "BEAR",
                underlying_atr=und_atr
            )

            if dec.new_trailing_sl > (pos.stop_loss or 0.0):
                pos.stop_loss = dec.new_trailing_sl
                db.commit()

            if dec.should_close:
                exit_triggered = True
                exit_reason = f"{dec.exit_reason}: {dec.state_description}"

        # Fallback Standard Conditions
        if not exit_triggered:
            # Condition 1: Automatic Stop Loss
            if cfg.auto_stop_loss and pos.stop_loss and ltp <= pos.stop_loss:
                exit_triggered = True
                exit_reason = f"STOP LOSS TRIGGERED: LTP Rs. {ltp} touched/breached stop Rs. {pos.stop_loss}"

            # Condition 2: Automatic Target
            elif cfg.auto_target and pos.target and ltp >= pos.target:
                exit_triggered = True
                exit_reason = f"TARGET REACHED: LTP Rs. {ltp} reached target Rs. {pos.target}"

            # Condition 3: Automatic Strategy Exit
            elif cfg.auto_strategy_exit and pos.strategy_code and not is_option:
                strat = STRATEGY_REGISTRY.get(pos.strategy_code)
                if strat:
                    candles = await market_service.get_historical_data(pos.symbol, timeframe="15m", limit=30)
                    if candles and len(candles) >= 20:
                        import pandas as pd
                        from .indicators import compute_all_indicators
                        df = pd.DataFrame([c.__dict__ for c in candles])
                        df = compute_all_indicators(df)
                        last = df.iloc[-1]
                        if float(last['ema20']) < float(last['ema50']):
                            exit_triggered = True
                            exit_reason = "STRATEGY EXIT: EMA20 crossed below EMA50 trend reversal"

        if exit_triggered:
            await self._execute_automatic_exit(pos, ltp, exit_reason, cfg, adapter, user_id, db)

    async def _execute_automatic_exit(self, pos: Position, exit_price: float, reason: str, cfg: AutomationConfig, adapter: Any, user_id: int, db: Session):
        order_client_id = f"auto_exit_{uuid.uuid4().hex[:10]}"

        # Send SELL order to broker
        res = await adapter.place_order(
            symbol=pos.symbol,
            side="SELL",
            quantity=pos.quantity,
            order_type="MARKET",
            price=exit_price,
            client_order_id=order_client_id
        )

        pnl = round((exit_price - pos.avg_price) * pos.quantity, 2)
        pos.status = "CLOSED"
        pos.closed_at = datetime.utcnow()
        pos.realized_pnl += pnl

        sell_order = Order(
            client_order_id=order_client_id,
            user_id=user_id,
            symbol=pos.symbol,
            side="SELL",
            order_type="MARKET",
            quantity=pos.quantity,
            price=exit_price,
            status="FILLED",
            broker=cfg.broker_name
        )
        db.add(sell_order)
        db.commit()
        db.refresh(sell_order)

        db.add(Trade(
            order_id=sell_order.id,
            user_id=user_id,
            symbol=pos.symbol,
            side="SELL",
            quantity=pos.quantity,
            price=exit_price,
            fees=10.0
        ))

        # Log timeline event
        db.add(AutomationLog(
            user_id=user_id,
            event_type="POSITION_CLOSED",
            symbol=pos.symbol,
            broker=cfg.broker_name,
            message=f"Automatic exit executed for {pos.symbol}: {reason}. Realized P&L: ₹{pnl}",
            details_json=json.dumps({"exit_price": exit_price, "pnl": pnl, "reason": reason})
        ))
        db.add(AuditLog(
            user_id=user_id,
            action="AUTO_EXIT",
            resource="POSITION",
            result="SUCCESS",
            metadata_json=json.dumps({"symbol": pos.symbol, "pnl": pnl, "reason": reason})
        ))
        db.commit()

    async def _evaluate_entries_for_user(self, user_id: int, cfg: AutomationConfig, adapter: Any, risk_cfg: RiskConfig, current_open_count: int, db: Session):
        """
        Evaluates configured watchlist symbols for new strategy entries.
        """
        is_index_options = any(k in (cfg.strategy_code or "") for k in ["STRAT_", "TREND", "RR_13", "SQUEEZE", "ORB", "REVERSION", "GAMMA", "VWAP", "CPR"])
        symbols = ["NIFTY", "BANKNIFTY"] if is_index_options else ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]
        strat = STRATEGY_REGISTRY.get(cfg.strategy_code, STRATEGY_REGISTRY["STRAT_ADAPTIVE_TREND_RIDER"])

        t_acc = db.scalar(select(TradingAccount).where(TradingAccount.user_id == user_id))
        base_capital = risk_cfg.capital if risk_cfg else 50000.0
        open_pos = db.scalars(select(Position).where(Position.user_id == user_id, Position.status == "OPEN")).all()
        invested_val = sum([p.quantity * p.avg_price for p in open_pos])
        available_cash = max(0.0, base_capital - invested_val)
        capital = base_capital

        for sym in symbols:
            # Skip if user already has an open position in this stock or option
            existing = db.scalar(select(Position).where(Position.user_id == user_id, Position.symbol.like(f"%{sym}%"), Position.status == "OPEN"))
            if existing:
                continue

            if is_index_options:
                c_15m = await market_service.get_historical_data(sym, timeframe="15m", limit=50)
                c_5m = await market_service.get_historical_data(sym, timeframe="5m", limit=50)
                c_1m = await market_service.get_historical_data(sym, timeframe="1m", limit=50)
                if not c_5m or len(c_5m) < 20:
                    continue
                sig = strat.evaluate(
                    underlying=sym,
                    candles_15m=c_15m,
                    candles_5m=c_5m,
                    candles_1m=c_1m,
                    capital=capital,
                    risk_pct=cfg.risk_per_trade_pct
                )
            else:
                candles = await market_service.get_historical_data(sym, timeframe="15m", limit=70)
                if not candles or len(candles) < 20:
                    continue
                try:
                    sig = strat.evaluate(
                        underlying=sym,
                        candles_15m=candles,
                        candles_5m=candles,
                        candles_1m=candles,
                        capital=capital,
                        risk_pct=cfg.risk_per_trade_pct
                    )
                except TypeError:
                    sig = strat.evaluate(sym, candles, capital=capital, risk_pct=cfg.risk_per_trade_pct)

            # Record timeline log for evaluation
            db.add(AutomationLog(
                user_id=user_id,
                event_type="STRATEGY_EVAL",
                symbol=sym,
                broker=cfg.broker_name,
                message=f"Strategy {cfg.strategy_code} evaluated {sym}: {sig.direction}",
                details_json=json.dumps({"direction": sig.direction, "reason": sig.reason})
            ))
            db.commit()

            is_buy = (sig.direction == "BUY") or (sig.direction in ["BUY_CE", "BUY_PE"] and getattr(sig, "option_contract", None) is not None)
            if is_buy:
                target_sym = getattr(sig, "option_symbol", sym) or sym
                # Validate Server-Side Risk
                risk_dec = validate_trade(
                    capital=capital,
                    daily_loss=0.0,
                    open_positions=current_open_count,
                    trades_today=0,
                    entry=sig.entry_price,
                    stop=sig.stop_loss,
                    target=sig.target,
                    available_cash=available_cash,
                    kill_switch_active=risk_cfg.kill_switch_active if risk_cfg else False,
                    market_feed_status=market_service.get_feed_status(),
                    risk_pct=cfg.risk_per_trade_pct,
                    daily_loss_limit=cfg.daily_loss_limit,
                    max_open_positions=cfg.max_open_positions,
                    max_trades_per_day=cfg.max_trades_per_day
                )

                if risk_dec.allowed and (getattr(sig, "quantity", 0) > 0 or risk_dec.quantity > 0):
                    if not getattr(sig, "quantity", 0):
                        sig.quantity = risk_dec.quantity
                    await self._execute_automatic_buy(target_sym, sig, cfg, adapter, user_id, db)
                    # Break after filling one order to prevent concurrent burst
                    break
                else:
                    db.add(AutomationLog(
                        user_id=user_id,
                        event_type="RISK_REJECTED",
                        symbol=target_sym,
                        broker=cfg.broker_name,
                        message=f"Risk check blocked entry for {target_sym}: {risk_dec.reason}",
                        details_json=json.dumps({"reason": risk_dec.reason})
                    ))
                    db.commit()

    async def _execute_automatic_buy(self, symbol: str, sig: Any, cfg: AutomationConfig, adapter: Any, user_id: int, db: Session):
        order_client_id = f"auto_{uuid.uuid4().hex[:10]}"

        # Step 1: Send BUY order to Broker
        order_res = await adapter.place_order(
            symbol=symbol,
            side="BUY",
            quantity=sig.quantity,
            order_type="MARKET",
            price=sig.entry_price,
            stop_loss=sig.stop_loss,
            target=sig.target,
            client_order_id=order_client_id
        )

        fill_price = sig.entry_price

        # Step 2: Record Order in DB
        order = Order(
            client_order_id=order_client_id,
            user_id=user_id,
            symbol=symbol,
            side="BUY",
            order_type="MARKET",
            quantity=sig.quantity,
            price=fill_price,
            stop_loss=sig.stop_loss,
            target=sig.target,
            status="FILLED",
            broker=cfg.broker_name
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        # Step 3: Record Trade & Events
        db.add(OrderEvent(order_id=order.id, from_status="VALIDATING", to_status="FILLED", details=f"Automated execution filled via {cfg.broker_name}"))
        db.add(Trade(
            order_id=order.id,
            user_id=user_id,
            symbol=symbol,
            side="BUY",
            quantity=sig.quantity,
            price=fill_price,
            fees=round(fill_price * sig.quantity * 0.0003, 2),
            slippage=round(fill_price * 0.0002, 2)
        ))

        # Step 4: Create Open Position
        pos = Position(
            user_id=user_id,
            symbol=symbol,
            quantity=sig.quantity,
            avg_price=fill_price,
            current_price=fill_price,
            stop_loss=sig.stop_loss,
            target=sig.target,
            strategy_code=cfg.strategy_code,
            status="OPEN"
        )
        db.add(pos)

        # Step 5: Timeline Log
        db.add(AutomationLog(
            user_id=user_id,
            event_type="ORDER_FILLED",
            symbol=symbol,
            broker=cfg.broker_name,
            message=f"Automated BUY filled: {sig.quantity} shares of {symbol} @ ₹{fill_price} via {cfg.broker_name}",
            details_json=json.dumps({"quantity": sig.quantity, "entry": fill_price, "stop": sig.stop_loss, "target": sig.target})
        ))
        db.add(AuditLog(
            user_id=user_id,
            action="AUTO_ORDER_FILLED",
            resource="ORDER",
            result="SUCCESS",
            metadata_json=json.dumps({"symbol": symbol, "qty": sig.quantity, "broker": cfg.broker_name})
        ))
        db.commit()

    async def _reconcile_broker_state(self, user_id: int, cfg: AutomationConfig, adapter: Any, internal_positions: List[Position], db: Session):
        """
        Compares internal position ledger with broker-reported state.
        If a mismatch is detected, halts automation to protect funds.
        """
        target_broker = "PAPER" if cfg.mode == "PAPER" else cfg.broker_name
        rec_res = await broker_manager.reconcile(user_id, target_broker, internal_positions, adapter)

        rec_record = ReconciliationRecord(
            user_id=user_id,
            broker=target_broker,
            status=rec_res["status"],
            mismatch_detected=rec_res["mismatch_detected"],
            details=json.dumps(rec_res)
        )
        db.add(rec_record)

        if rec_res["mismatch_detected"]:
            # Safety rule: Pause automation when reconciliation disagrees
            cfg.is_running = False
            db.add(RiskEvent(
                user_id=user_id,
                event_type="RECONCILIATION_MISMATCH",
                message=f"Broker position mismatch detected on {cfg.broker_name}. Automation paused automatically for safety."
            ))
            db.add(AutomationLog(
                user_id=user_id,
                event_type="RECONCILIATION",
                symbol="",
                broker=cfg.broker_name,
                message="BROKER RECONCILIATION ERROR: Internal positions and broker state disagree. Automation PAUSED.",
                details_json=json.dumps(rec_res)
            ))

        db.commit()

    def _resolve_user_adapter(self, user_id: int, cfg: AutomationConfig, db: Session) -> Any:
        b_name = cfg.broker_name.upper()
        if b_name == "PAPER" or cfg.mode == "PAPER":
            return broker_manager.get_adapter("PAPER")

        conn = db.scalar(select(BrokerConnection).where(
            BrokerConnection.user_id == user_id,
            BrokerConnection.broker_name == b_name,
            BrokerConnection.is_connected == True
        ))
        if conn:
            raw_token = decrypt_secret(conn.encrypted_token)
            return broker_manager.get_adapter(
                b_name,
                access_token=raw_token,
                client_id=conn.client_id,
                api_key=conn.api_key
            )
        return broker_manager.get_adapter("PAPER")

    async def emergency_exit_all(self, user_id: int, db: Session) -> Dict[str, Any]:
        """
        Emergency Kill Switch: Stops automation immediately and exits ALL open positions at market price.
        """
        # Stop automation
        cfg = db.scalar(select(AutomationConfig).where(AutomationConfig.user_id == user_id))
        if cfg:
            cfg.is_running = False

        open_positions = db.scalars(select(Position).where(Position.user_id == user_id, Position.status == "OPEN")).all()
        exited = []

        adapter = self._resolve_user_adapter(user_id, cfg or AutomationConfig(), db)

        for p in open_positions:
            quote = await market_service.get_quote(p.symbol)
            exit_price = quote.ltp if quote else p.current_price
            await self._execute_automatic_exit(
                p,
                exit_price,
                "EMERGENCY KILL SWITCH: User commanded full exit of all open positions",
                cfg or AutomationConfig(broker_name="PAPER"),
                adapter,
                user_id,
                db
            )
            exited.append(p.symbol)

        db.add(RiskEvent(
            user_id=user_id,
            event_type="EMERGENCY_EXIT_ALL",
            message=f"Emergency Kill Switch triggered: Closed {len(exited)} open positions ({', '.join(exited)})"
        ))
        db.commit()

        return {"status": "SUCCESS", "closed_positions": exited, "count": len(exited)}

automation_engine = AutomationEngine()
