from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime
import pandas as pd
from .indicators import compute_all_indicators
from .market_data import Candle

@dataclass
class SignalResult:
    signal_id: str
    symbol: str
    strategy_code: str
    strategy_version: str
    direction: str  # BUY, SELL, NO_TRADE
    entry_price: float
    stop_loss: float
    target: float
    quantity: int
    risk_amount: float
    risk_reward: float
    confidence: float
    timestamp: str
    reason: str

class BaseStrategy:
    code = "BASE"
    name = "Base Strategy"
    version = "1.0.0"

    def evaluate(self, symbol: str, candles: List[Candle], capital: float = 10000.0, risk_pct: float = 0.01) -> SignalResult:
        raise NotImplementedError

class StrategyEMAVWAPTrend(BaseStrategy):
    """
    Strategy 1: EMA/VWAP Trend
    Long conditions:
    EMA20 > EMA50 AND Close > VWAP AND RSI > 50
    Stop: ATR-based (1.5 * ATR)
    Target: 1:3 RR
    """
    code = "STRAT_EMA_VWAP"
    name = "EMA/VWAP Trend"
    version = "1.0.0"

    def evaluate(self, symbol: str, candles: List[Candle], capital: float = 10000.0, risk_pct: float = 0.01) -> SignalResult:
        sig_id = f"sig_{uuid.uuid4().hex[:10]}"
        now_str = datetime.utcnow().isoformat()

        if len(candles) < 50:
            return SignalResult(
                signal_id=sig_id, symbol=symbol, strategy_code=self.code, strategy_version=self.version,
                direction="NO_TRADE", entry_price=0.0, stop_loss=0.0, target=0.0, quantity=0,
                risk_amount=0.0, risk_reward=3.0, confidence=0.0, timestamp=now_str,
                reason="Insufficient historical candles (< 50)"
            )

        df = pd.DataFrame([c.__dict__ for c in candles])
        df = compute_all_indicators(df)
        last = df.iloc[-1]

        c = last['close']
        ema20 = last['ema20']
        ema50 = last['ema50']
        vwap = last['vwap']
        rsi = last['rsi14']
        atr = last['atr14'] if not pd.isna(last['atr14']) and last['atr14'] > 0 else c * 0.01

        vol = last['volume']
        avg_vol = df['volume'].rolling(20).mean().iloc[-1] if len(df) >= 20 else vol
        vol_ok = (vol >= avg_vol * 0.8) if avg_vol > 0 else True

        # Check Long conditions: EMA20 > EMA50, Price > VWAP, RSI > 50, Volume confirmation
        if ema20 > ema50 and c > vwap and rsi > 50 and vol_ok:
            entry = round(c, 2)
            stop_dist = round(1.5 * atr, 2)
            stop_loss = round(entry - stop_dist, 2)
            target = round(entry + (3.0 * stop_dist), 2)

            planned_risk = capital * risk_pct
            qty = max(1, int(planned_risk // max(stop_dist, 0.05)))
            actual_risk = round(qty * stop_dist, 2)

            return SignalResult(
                signal_id=sig_id, symbol=symbol, strategy_code=self.code, strategy_version=self.version,
                direction="BUY", entry_price=entry, stop_loss=stop_loss, target=target, quantity=qty,
                risk_amount=actual_risk, risk_reward=3.0, confidence=0.88, timestamp=now_str,
                reason=f"Bullish Trend: EMA20 ({ema20:.1f}) > EMA50 ({ema50:.1f}), Close ({c:.1f}) > VWAP ({vwap:.1f}), RSI ({rsi:.1f}) > 50, Vol ({vol:,.0f} >= {avg_vol:,.0f})"
            )

        return SignalResult(
            signal_id=sig_id, symbol=symbol, strategy_code=self.code, strategy_version=self.version,
            direction="NO_TRADE", entry_price=round(c, 2), stop_loss=0.0, target=0.0, quantity=0,
            risk_amount=0.0, risk_reward=3.0, confidence=0.0, timestamp=now_str,
            reason=f"Trend conditions not met (EMA20: {ema20:.1f}, EMA50: {ema50:.1f}, RSI: {rsi:.1f}, VWAP: {vwap:.1f})"
        )

class StrategyOpeningRangeBreakout(BaseStrategy):
    """
    Strategy 2: Opening Range Breakout (ORB 15m)
    Long: Price breaks Opening Range High AND Volume confirmation (RVOL > 1.0)
    Stop: Opening Range Low
    Target: 1:3 RR
    """
    code = "STRAT_ORB"
    name = "Opening Range Breakout"
    version = "1.0.0"

    def evaluate(self, symbol: str, candles: List[Candle], capital: float = 10000.0, risk_pct: float = 0.01) -> SignalResult:
        sig_id = f"sig_{uuid.uuid4().hex[:10]}"
        now_str = datetime.utcnow().isoformat()

        if len(candles) < 20:
            return SignalResult(
                signal_id=sig_id, symbol=symbol, strategy_code=self.code, strategy_version=self.version,
                direction="NO_TRADE", entry_price=0.0, stop_loss=0.0, target=0.0, quantity=0,
                risk_amount=0.0, risk_reward=3.0, confidence=0.0, timestamp=now_str,
                reason="Insufficient historical candles for ORB"
            )

        df = pd.DataFrame([c.__dict__ for c in candles])
        df = compute_all_indicators(df)

        # Opening range: initial window (first candle of session or recent range)
        or_candles = df.iloc[-15:-1] if len(df) >= 15 else df.iloc[:-1]
        or_high = or_candles['high'].max()
        or_low = or_candles['low'].min()

        last = df.iloc[-1]
        c = last['close']
        rvol = last['rvol']

        if c > or_high and rvol >= 1.0:
            entry = round(c, 2)
            stop_loss = round(or_low, 2)
            stop_dist = max(round(entry - stop_loss, 2), 0.5)
            target = round(entry + (3.0 * stop_dist), 2)

            planned_risk = capital * risk_pct
            qty = max(1, int(planned_risk // stop_dist))
            actual_risk = round(qty * stop_dist, 2)

            return SignalResult(
                signal_id=sig_id, symbol=symbol, strategy_code=self.code, strategy_version=self.version,
                direction="BUY", entry_price=entry, stop_loss=stop_loss, target=target, quantity=qty,
                risk_amount=actual_risk, risk_reward=3.0, confidence=0.88, timestamp=now_str,
                reason=f"ORB Breakout: Close ({c:.2f}) broke OR High ({or_high:.2f}) with RVOL {rvol:.2f}"
            )

        return SignalResult(
            signal_id=sig_id, symbol=symbol, strategy_code=self.code, strategy_version=self.version,
            direction="NO_TRADE", entry_price=round(c, 2), stop_loss=0.0, target=0.0, quantity=0,
            risk_amount=0.0, risk_reward=3.0, confidence=0.0, timestamp=now_str,
            reason=f"No ORB breakout: Close {c:.2f} within range [{or_low:.2f} - {or_high:.2f}]"
        )

class StrategyVWAPPullback(BaseStrategy):
    """
    Strategy 3: VWAP Pullback
    Long conditions:
    Trend is bullish (EMA20 > EMA50) AND Price pulls toward VWAP (abs(Close - VWAP) <= 0.5 * ATR)
    AND Bullish confirmation (Close > Open)
    Stop: ATR-based
    Target: 1:3 RR
    """
    code = "STRAT_VWAP_PULLBACK"
    name = "VWAP Pullback"
    version = "1.0.0"

    def evaluate(self, symbol: str, candles: List[Candle], capital: float = 10000.0, risk_pct: float = 0.01) -> SignalResult:
        sig_id = f"sig_{uuid.uuid4().hex[:10]}"
        now_str = datetime.utcnow().isoformat()

        if len(candles) < 50:
            return SignalResult(
                signal_id=sig_id, symbol=symbol, strategy_code=self.code, strategy_version=self.version,
                direction="NO_TRADE", entry_price=0.0, stop_loss=0.0, target=0.0, quantity=0,
                risk_amount=0.0, risk_reward=3.0, confidence=0.0, timestamp=now_str,
                reason="Insufficient candles for VWAP Pullback"
            )

        df = pd.DataFrame([c.__dict__ for c in candles])
        df = compute_all_indicators(df)
        last = df.iloc[-1]

        c = last['close']
        o = last['open']
        ema20 = last['ema20']
        ema50 = last['ema50']
        vwap = last['vwap']
        atr = last['atr14'] if not pd.isna(last['atr14']) and last['atr14'] > 0 else c * 0.01

        is_bullish_trend = ema20 > ema50
        near_vwap = abs(c - vwap) <= (0.75 * atr)
        bullish_candle = c >= o

        if is_bullish_trend and near_vwap and bullish_candle:
            entry = round(c, 2)
            stop_dist = round(1.2 * atr, 2)
            stop_loss = round(entry - stop_dist, 2)
            target = round(entry + (3.0 * stop_dist), 2)

            planned_risk = capital * risk_pct
            qty = max(1, int(planned_risk // max(stop_dist, 0.05)))
            actual_risk = round(qty * stop_dist, 2)

            return SignalResult(
                signal_id=sig_id, symbol=symbol, strategy_code=self.code, strategy_version=self.version,
                direction="BUY", entry_price=entry, stop_loss=stop_loss, target=target, quantity=qty,
                risk_amount=actual_risk, risk_reward=3.0, confidence=0.82, timestamp=now_str,
                reason=f"VWAP Pullback: Bullish trend with bounce near VWAP ({vwap:.1f}), close ({c:.1f}) > open ({o:.1f})"
            )

        return SignalResult(
            signal_id=sig_id, symbol=symbol, strategy_code=self.code, strategy_version=self.version,
            direction="NO_TRADE", entry_price=round(c, 2), stop_loss=0.0, target=0.0, quantity=0,
            risk_amount=0.0, risk_reward=3.0, confidence=0.0, timestamp=now_str,
            reason="Price not in confirmed VWAP pullback zone"
        )

STRATEGY_REGISTRY = {
    "STRAT_EMA_VWAP": StrategyEMAVWAPTrend(),
    "STRAT_EMA_VWAP_RSI": StrategyEMAVWAPTrend(),
    "STRAT_ORB": StrategyOpeningRangeBreakout(),
    "STRAT_VWAP_PULLBACK": StrategyVWAPPullback()
}

def resolve_strategy(strategy_code: str) -> Optional[BaseStrategy]:
    if not strategy_code:
        return STRATEGY_REGISTRY["STRAT_EMA_VWAP"]
    code = strategy_code.upper().strip()
    if code in STRATEGY_REGISTRY:
        return STRATEGY_REGISTRY[code]
    if "EMA" in code and "VWAP" in code:
        return STRATEGY_REGISTRY["STRAT_EMA_VWAP"]
    if "ORB" in code or "BREAKOUT" in code:
        return STRATEGY_REGISTRY["STRAT_ORB"]
    if "PULLBACK" in code or "VWAP" in code:
        return STRATEGY_REGISTRY["STRAT_VWAP_PULLBACK"]
    return STRATEGY_REGISTRY.get("STRAT_EMA_VWAP")
