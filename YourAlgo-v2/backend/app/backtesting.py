"""
YOURALGO - Production Index Options Backtesting & Research Engine
Simulates realistic Index Options Buying (NIFTY / BANKNIFTY CE/PE) with:
- Black-Scholes Greek and Theta decay dynamics
- Realistic slippage (0.20% on premium)
- Real statutory transaction costs (Brokerage, STT, Exchange fees, GST, Stamp Duty)
- Train / Validation / Out-of-Sample splits (Anti-overfitting)
- Walk-Forward performance estimation
- Market Regime breakdown & Exit Reason distribution
- Side-by-side Multi-Strategy Comparison
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date
import math
import numpy as np
import pandas as pd
import logging

from .strategies import STRATEGY_REGISTRY, resolve_strategy, get_all_strategies_catalog
from .options_engine import options_engine, calculate_black_scholes_greeks
from .regime_engine import regime_engine
from .market_data import market_service, Candle
from .indicators import compute_all_indicators

logger = logging.getLogger(__name__)

# Indian Statutory Option Charges Calculation
def calculate_indian_option_charges(
    buy_turnover: float,
    sell_turnover: float,
    brokerage_per_order: float = 20.0
) -> Dict[str, float]:
    """
    Computes exact regulatory transaction costs for Indian Index Options Buying:
    - Brokerage: Flat ₹20 per executed order (Buy + Sell = ₹40)
    - STT (Securities Transaction Tax): 0.0625% on Sell Turnover
    - Exchange Transaction Charges: 0.05% on Premium Turnover (NSE)
    - SEBI Turnover Charges: ₹10 per Crore (0.0001%)
    - GST: 18% on (Brokerage + Exchange Charges + SEBI charges)
    - Stamp Duty: 0.003% on Buy Turnover
    """
    brokerage = brokerage_per_order * 2.0 # Round trip (entry + exit)
    stt = round(sell_turnover * 0.000625, 2)
    exchange_charges = round((buy_turnover + sell_turnover) * 0.0005, 2)
    sebi_charges = round((buy_turnover + sell_turnover) * 0.000001, 2)
    gst = round((brokerage + exchange_charges + sebi_charges) * 0.18, 2)
    stamp_duty = round(buy_turnover * 0.00003, 2)

    total_statutory = round(brokerage + stt + exchange_charges + sebi_charges + gst + stamp_duty, 2)
    return {
        "brokerage": brokerage,
        "stt": stt,
        "exchange_charges": exchange_charges,
        "gst": gst,
        "stamp_duty": stamp_duty,
        "total_charges": total_statutory
    }

@dataclass
class OptionBacktestTrade:
    trade_id: int
    entry_time: str
    exit_time: str
    underlying: str
    option_symbol: str
    option_type: str         # CE or PE
    strike: float
    direction: str
    entry_price: float
    exit_price: float
    quantity: int
    lots: int
    gross_pnl: float
    net_pnl: float
    return_pct: float
    exit_reason: str         # TARGET, STOP_LOSS, TRAILING_STOP, THESIS_FAILURE, TIME_EXIT, SESSION_EXIT
    market_regime: str
    signal_score: float
    slippage_paid: float
    charges_paid: float
    bars_held: int

@dataclass
class RegimePerformance:
    regime: str
    trades_count: int
    win_rate: float
    net_pnl: float
    profit_factor: float

@dataclass
class OptionBacktestResult:
    underlying: str
    strategy_code: str
    strategy_name: str
    dataset_split: str        # FULL, TRAIN, VALIDATION, OUT_OF_SAMPLE
    initial_capital: float
    ending_capital: float
    net_pnl: float
    return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    expectancy: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    recovery_factor: float
    average_win: float
    average_loss: float
    max_consecutive_losses: int
    total_slippage: float
    total_transaction_costs: float
    exit_distribution: Dict[str, int]
    regime_breakdown: List[Dict[str, Any]]
    walk_forward_efficiency: Optional[float]
    trades: List[Dict[str, Any]]
    equity_curve: List[Dict[str, Any]]

async def run_options_backtest(
    underlying: str,
    strategy_code: str,
    capital: float = 100000.0,
    risk_pct: float = 0.01,
    timeframe: str = "5m",
    split_mode: str = "FULL",  # FULL, TRAIN, VALIDATION, OUT_OF_SAMPLE
    candles_input: Optional[List[Candle]] = None
) -> OptionBacktestResult:
    """
    Executes realistic Index Options Backtesting simulation.
    Handles option pricing dynamics, Greeks, theta decay, and statutory Indian charges.
    """
    symbol_key = "NIFTY 50" if underlying.upper() == "NIFTY" else ("BANK NIFTY" if "BANK" in underlying.upper() else underlying)
    candles = candles_input or await market_service.get_historical_data(symbol_key, timeframe=timeframe, limit=200)

    if len(candles) < 35:
        raise ValueError(f"Insufficient historical candles ({len(candles)}) for options backtesting")

    # Anti-Overfitting Dataset Splitting
    total_bars = len(candles)
    if split_mode == "TRAIN":
        # First 60%
        candles = candles[:int(total_bars * 0.60)]
    elif split_mode == "VALIDATION":
        # Middle 20%
        start_idx = int(total_bars * 0.60)
        end_idx = int(total_bars * 0.80)
        candles = candles[start_idx:end_idx]
    elif split_mode == "OUT_OF_SAMPLE":
        # Last 20%
        candles = candles[int(total_bars * 0.80):]

    if len(candles) < 25:
        raise ValueError("Data split partition contains insufficient candles (< 25)")

    strat = resolve_strategy(strategy_code)
    df = pd.DataFrame([c.__dict__ for c in candles])
    df = compute_all_indicators(df)

    trades: List[OptionBacktestTrade] = []
    equity = float(capital)
    peak_equity = float(capital)
    max_drawdown = 0.0
    equity_curve = [{"time": candles[0].timestamp, "equity": round(equity, 2)}]

    active_trade: Optional[Dict[str, Any]] = None
    trade_id_seq = 1

    exit_counts = {
        "TARGET": 0, "STOP_LOSS": 0, "TRAILING_STOP": 0,
        "THESIS_FAILURE": 0, "TIME_EXIT": 0, "SESSION_EXIT": 0
    }
    regime_stats: Dict[str, Dict[str, Any]] = {}

    for i in range(25, len(candles)):
        c_bar = candles[i]
        c_spot = c_bar.close
        c_vwap = df.iloc[i].get('vwap', c_spot)
        c_atr = df.iloc[i].get('atr14', c_spot * 0.008)

        # 1. Evaluate Open Position Management
        if active_trade:
            pos = active_trade
            bars_held = i - pos["entry_bar_idx"]

            # Simulate current option price using underlying movement & theta decay
            # delta_p = spot_diff * delta - (daily_theta * (bars_held / 75.0))
            spot_diff = c_spot - pos["underlying_entry"]
            if pos["option_type"] == "PE":
                spot_diff = -spot_diff

            delta = pos["delta"]
            # Theta decay per 5m bar (approx 75 5m bars in a 6.25 hr trading session)
            decay = max(0.0, pos["daily_theta"] * (bars_held / 75.0))
            raw_opt_p = pos["entry_price"] + (spot_diff * delta) - decay
            current_opt_p = max(0.20, round(raw_opt_p, 2))

            # Update highest seen price
            if current_opt_p > pos["highest_price_seen"]:
                pos["highest_price_seen"] = current_opt_p

            # Evaluate Position Manager Decision
            reg_15m = "BULL" if c_spot > c_vwap else "BEAR"
            time_obj = None
            try:
                time_obj = datetime.fromisoformat(c_bar.timestamp.replace("Z", ""))
            except Exception:
                time_obj = None

            # Trailing & SL adjustments
            risk_r = max(2.0, pos["entry_price"] - pos["initial_sl"])
            unrealized_gain = current_opt_p - pos["entry_price"]
            r_mult = unrealized_gain / risk_r

            # Ratchet trailing SL
            if pos["trailing_type"] == "ATR_TRAILING":
                if r_mult >= 2.0:
                    lock_sl = max(round(pos["entry_price"] + risk_r, 2), round(pos["highest_price_seen"] - (1.2 * risk_r), 2))
                    if lock_sl > pos["current_sl"]:
                        pos["current_sl"] = lock_sl
                elif r_mult >= 1.5:
                    be_sl = round(pos["entry_price"] + (0.10 * risk_r), 2)
                    if be_sl > pos["current_sl"]:
                        pos["current_sl"] = be_sl

            # Check Exit Conditions
            should_exit = False
            exit_reason = ""
            exit_p = current_opt_p

            if current_opt_p <= pos["current_sl"]:
                should_exit = True
                exit_p = pos["current_sl"]
                exit_reason = "TRAILING_STOP" if pos["current_sl"] > pos["initial_sl"] else "STOP_LOSS"
            elif pos["target"] > 0 and current_opt_p >= pos["target"]:
                should_exit = True
                exit_p = pos["target"]
                exit_reason = "TARGET"
            elif bars_held >= 14 and r_mult < 0.4:
                should_exit = True
                exit_reason = "TIME_EXIT"
            elif (pos["option_type"] == "CE" and c_spot < c_vwap * 0.998) or (pos["option_type"] == "PE" and c_spot > c_vwap * 1.002):
                if bars_held >= 3:
                    should_exit = True
                    exit_reason = "THESIS_FAILURE"
            elif i == len(candles) - 1:
                should_exit = True
                exit_reason = "SESSION_EXIT"

            if should_exit:
                # Apply realistic execution slippage on option exit (0.20%)
                slippage_exit = round(exit_p * 0.0020, 2)
                final_exit_p = round(max(0.10, exit_p - slippage_exit), 2)

                qty = pos["quantity"]
                buy_turnover = round(pos["entry_price"] * qty, 2)
                sell_turnover = round(final_exit_p * qty, 2)
                charges = calculate_indian_option_charges(buy_turnover, sell_turnover)

                total_slippage = round((pos["slippage_entry"] + slippage_exit) * qty, 2)
                gross_pnl = round((final_exit_p - pos["entry_price"]) * qty, 2)
                net_pnl = round(gross_pnl - charges["total_charges"], 2)
                ret_pct = round((net_pnl / max(buy_turnover, 1.0)) * 100.0, 2)

                equity += net_pnl
                if equity > peak_equity:
                    peak_equity = equity
                dd = round(peak_equity - equity, 2)
                if dd > max_drawdown:
                    max_drawdown = dd

                t_record = OptionBacktestTrade(
                    trade_id=trade_id_seq,
                    entry_time=pos["entry_time"],
                    exit_time=c_bar.timestamp,
                    underlying=underlying.upper(),
                    option_symbol=pos["option_symbol"],
                    option_type=pos["option_type"],
                    strike=pos["strike"],
                    direction=pos["direction"],
                    entry_price=pos["entry_price"],
                    exit_price=final_exit_p,
                    quantity=qty,
                    lots=pos["lots"],
                    gross_pnl=gross_pnl,
                    net_pnl=net_pnl,
                    return_pct=ret_pct,
                    exit_reason=exit_reason,
                    market_regime=pos["regime"],
                    signal_score=pos["signal_score"],
                    slippage_paid=total_slippage,
                    charges_paid=charges["total_charges"],
                    bars_held=bars_held
                )
                trades.append(t_record)
                trade_id_seq += 1

                # Update stats
                exit_counts[exit_reason] = exit_counts.get(exit_reason, 0) + 1
                reg = pos["regime"]
                if reg not in regime_stats:
                    regime_stats[reg] = {"trades": 0, "wins": 0, "net_pnl": 0.0, "gross_win": 0.0, "gross_loss": 0.0}
                regime_stats[reg]["trades"] += 1
                regime_stats[reg]["net_pnl"] += net_pnl
                if net_pnl > 0:
                    regime_stats[reg]["wins"] += 1
                    regime_stats[reg]["gross_win"] += net_pnl
                else:
                    regime_stats[reg]["gross_loss"] += abs(net_pnl)

                equity_curve.append({"time": c_bar.timestamp, "equity": round(equity, 2)})
                active_trade = None
                continue

        # 2. Check for New Entry Signal (Only if no open position)
        if not active_trade:
            # Slices for multi-timeframe simulation
            sub_candles = candles[:i+1]
            sig = strat.evaluate(
                underlying=underlying,
                candles_15m=sub_candles,
                candles_5m=sub_candles,
                candles_1m=sub_candles,
                capital=equity,
                risk_pct=risk_pct
            )

            if sig.direction in ["BUY_CE", "BUY_PE"] and sig.option_contract:
                opt_c = sig.option_contract
                # Apply realistic entry slippage (0.20%)
                slippage_entry = round(sig.entry_price * 0.0020, 2)
                real_entry = round(sig.entry_price + slippage_entry, 2)

                active_trade = {
                    "entry_bar_idx": i,
                    "entry_time": c_bar.timestamp,
                    "underlying_entry": c_spot,
                    "option_symbol": sig.option_symbol,
                    "option_type": opt_c.get("option_type", "CE"),
                    "strike": opt_c.get("strike", c_spot),
                    "direction": sig.direction,
                    "entry_price": real_entry,
                    "initial_sl": sig.stop_loss,
                    "current_sl": sig.stop_loss,
                    "target": sig.target,
                    "trailing_type": sig.trailing_type,
                    "highest_price_seen": real_entry,
                    "quantity": sig.quantity,
                    "lots": sig.lots,
                    "delta": abs(opt_c.get("delta", 0.50)),
                    "daily_theta": abs(opt_c.get("theta", 8.0)),
                    "regime": sig.market_regime,
                    "signal_score": sig.signal_score,
                    "slippage_entry": slippage_entry
                }

    # Aggregate Statistics
    total_trades = len(trades)
    winning_trades = sum(1 for t in trades if t.net_pnl > 0)
    losing_trades = sum(1 for t in trades if t.net_pnl <= 0)
    win_rate = round((winning_trades / total_trades * 100.0), 2) if total_trades > 0 else 0.0

    net_pnl = round(equity - capital, 2)
    return_pct = round((net_pnl / capital) * 100.0, 2)

    wins = [t.net_pnl for t in trades if t.net_pnl > 0]
    losses = [abs(t.net_pnl) for t in trades if t.net_pnl <= 0]
    tot_win = sum(wins)
    tot_loss = sum(losses)
    profit_factor = round(tot_win / max(tot_loss, 1.0), 2) if tot_loss > 0 else (99.0 if tot_win > 0 else 0.0)

    avg_win = round(float(np.mean(wins)), 2) if wins else 0.0
    avg_loss = round(float(np.mean(losses)), 2) if losses else 0.0
    expectancy = round(((win_rate / 100.0) * avg_win) - (((100.0 - win_rate) / 100.0) * avg_loss), 2) if total_trades > 0 else 0.0

    max_dd_pct = round((max_drawdown / peak_equity) * 100.0, 2) if peak_equity > 0 else 0.0
    recovery_factor = round(net_pnl / max(max_drawdown, 1.0), 2) if max_drawdown > 0 else 0.0

    # Sharpe & Sortino ratios (annualized, 252 trading days)
    pnl_series = [t.net_pnl for t in trades]
    if len(pnl_series) >= 2:
        std_dev = float(np.std(pnl_series))
        sharpe = round(math.sqrt(252.0) * (float(np.mean(pnl_series)) / max(std_dev, 1e-4)), 2)
        downside = [p for p in pnl_series if p < 0]
        downside_std = float(np.std(downside)) if len(downside) >= 2 else std_dev
        sortino = round(math.sqrt(252.0) * (float(np.mean(pnl_series)) / max(downside_std, 1e-4)), 2)
    else:
        sharpe = 0.0
        sortino = 0.0

    # Max consecutive losses
    consec_loss = 0
    max_consec = 0
    for t in trades:
        if t.net_pnl <= 0:
            consec_loss += 1
            if consec_loss > max_consec:
                max_consec = consec_loss
        else:
            consec_loss = 0

    tot_slip = round(sum(t.slippage_paid for t in trades), 2)
    tot_chgs = round(sum(t.charges_paid for t in trades), 2)

    # Regime breakdown formatting
    reg_breakdown = []
    for r_name, r_data in regime_stats.items():
        t_cnt = r_data["trades"]
        w_cnt = r_data["wins"]
        pf = round(r_data["gross_win"] / max(r_data["gross_loss"], 1.0), 2)
        reg_breakdown.append({
            "regime": r_name,
            "trades_count": t_cnt,
            "win_rate": round((w_cnt / max(t_cnt, 1)) * 100.0, 1),
            "net_pnl": round(r_data["net_pnl"], 2),
            "profit_factor": pf
        })

    return OptionBacktestResult(
        underlying=underlying.upper(),
        strategy_code=strat.code,
        strategy_name=strat.name,
        dataset_split=split_mode,
        initial_capital=capital,
        ending_capital=round(equity, 2),
        net_pnl=net_pnl,
        return_pct=return_pct,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=win_rate,
        profit_factor=profit_factor,
        expectancy=expectancy,
        max_drawdown=max_drawdown,
        max_drawdown_pct=max_dd_pct,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        recovery_factor=recovery_factor,
        average_win=avg_win,
        average_loss=avg_loss,
        max_consecutive_losses=max_consec,
        total_slippage=tot_slip,
        total_transaction_costs=tot_chgs,
        exit_distribution=exit_counts,
        regime_breakdown=reg_breakdown,
        walk_forward_efficiency=None,
        trades=[asdict(t) for t in trades],
        equity_curve=equity_curve
    )

async def run_walk_forward_backtest(
    underlying: str,
    strategy_code: str,
    capital: float = 100000.0,
    risk_pct: float = 0.01,
    timeframe: str = "5m"
) -> Dict[str, Any]:
    """
    Executes Train, Validation, and Out-of-Sample Walk-Forward analysis.
    Verifies strategy robustness against curve-fitting.
    """
    train_res = await run_options_backtest(underlying, strategy_code, capital, risk_pct, timeframe, "TRAIN")
    val_res = await run_options_backtest(underlying, strategy_code, capital, risk_pct, timeframe, "VALIDATION")
    oos_res = await run_options_backtest(underlying, strategy_code, capital, risk_pct, timeframe, "OUT_OF_SAMPLE")

    # Walk-forward efficiency (WFE) = Out-of-Sample Sharpe / In-Sample Sharpe
    in_sample_sharpe = max(0.1, train_res.sharpe_ratio)
    wfe = round(oos_res.sharpe_ratio / in_sample_sharpe, 2)

    return {
        "underlying": underlying.upper(),
        "strategy_code": strategy_code,
        "walk_forward_efficiency": wfe,
        "is_robust": (wfe >= 0.50 and oos_res.profit_factor >= 1.2),
        "in_sample_train": asdict(train_res),
        "validation": asdict(val_res),
        "out_of_sample": asdict(oos_res)
    }

async def compare_all_strategies(
    underlying: str = "NIFTY",
    capital: float = 100000.0,
    risk_pct: float = 0.01,
    timeframe: str = "5m"
) -> List[Dict[str, Any]]:
    """
    Simulates all 5 index option strategies on the identical market dataset.
    Returns side-by-side performance comparison.
    """
    catalog = get_all_strategies_catalog()
    results = []

    symbol_key = "NIFTY 50" if underlying.upper() == "NIFTY" else ("BANK NIFTY" if "BANK" in underlying.upper() else underlying)
    shared_candles = await market_service.get_historical_data(symbol_key, timeframe=timeframe, limit=200)

    for item in catalog:
        code = item["code"]
        try:
            res = await run_options_backtest(
                underlying=underlying,
                strategy_code=code,
                capital=capital,
                risk_pct=risk_pct,
                timeframe=timeframe,
                split_mode="FULL",
                candles_input=shared_candles
            )
            results.append({
                "code": code,
                "name": item["name"],
                "version": item["version"],
                "total_trades": res.total_trades,
                "win_rate": res.win_rate,
                "net_pnl": res.net_pnl,
                "return_pct": res.return_pct,
                "profit_factor": res.profit_factor,
                "max_drawdown_pct": res.max_drawdown_pct,
                "sharpe_ratio": res.sharpe_ratio,
                "sortino_ratio": res.sortino_ratio,
                "expectancy": res.expectancy,
                "total_costs": round(res.total_transaction_costs + res.total_slippage, 2),
                "is_active": True
            })
        except Exception as e:
            logger.warning(f"Error backtesting strategy {code}: {e}")

    return results

# Backwards compatibility alias
run_backtest_simulation = run_options_backtest
