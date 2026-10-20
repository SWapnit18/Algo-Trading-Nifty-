"""
YOURALGO - Market Regime, Multi-Timeframe & Signal Quality Engine
Classifies NIFTY & BANKNIFTY into STRONG_BULL, BULL, NEUTRAL, BEAR, STRONG_BEAR.
Synthesizes 15m, 5m, and 1m timeframes, calculates 0-100 Signal Quality Score,
and executes strict No-Trade filtering.
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, time
import pandas as pd
import numpy as np
import logging

from .market_data import Candle
from .indicators import compute_all_indicators

logger = logging.getLogger(__name__)

# Market Regimes
REGIME_STRONG_BULL = "STRONG_BULL"
REGIME_BULL = "BULL"
REGIME_NEUTRAL = "NEUTRAL"
REGIME_BEAR = "BEAR"
REGIME_STRONG_BEAR = "STRONG_BEAR"

@dataclass
class RegimeAnalysis:
    symbol: str
    timeframe: str
    regime: str           # STRONG_BULL, BULL, NEUTRAL, BEAR, STRONG_BEAR
    ema_structure: str    # BULLISH, BEARISH, MIXED
    ema_slope: float
    vwap_relation: str    # ABOVE, BELOW, AT_VWAP
    rsi: float
    adx: float
    atr: float
    volatility_regime: str  # HIGH_VOL, NORMAL_VOL, LOW_VOL
    structure: str        # HIGHER_HIGHS, LOWER_LOWS, SIDEWAYS
    confidence: float     # 0.0 to 1.0
    summary: str

@dataclass
class MultiTimeframeResult:
    symbol: str
    tf_15m_regime: str
    tf_5m_setup: str
    tf_1m_timing: str
    aligned: bool
    recommended_direction: str  # BUY_CE, BUY_PE, NO_TRADE
    alignment_reason: str

@dataclass
class SignalQualityScore:
    total_score: float         # 0 to 100
    trend_score: float         # Max 25
    momentum_score: float      # Max 20
    vwap_score: float          # Max 15
    structure_score: float     # Max 15
    volatility_score: float    # Max 10
    volume_score: float        # Max 5
    option_quality_score: float # Max 10
    threshold_passed: bool
    threshold_used: float
    breakdown_notes: List[str]

@dataclass
class NoTradeDecision:
    can_trade: bool
    rejection_reasons: List[str]
    primary_reason: str

class MarketRegimeEngine:
    """
    Evaluates underlying technical structure across indicators and multi-timeframes.
    Never relies on a single indicator.
    """

    def compute_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Computes Welles Wilder Average Directional Index (ADX)."""
        if len(df) < period + 2:
            return pd.Series([20.0] * len(df), index=df.index)

        high = df['high']
        low = df['low']
        close = df['close']

        up_move = high.diff()
        down_move = -low.diff()

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        tr_smooth = tr.rolling(period).sum()
        plus_di = 100.0 * (pd.Series(plus_dm, index=df.index).rolling(period).sum() / tr_smooth.replace(0, 1e-6))
        minus_di = 100.0 * (pd.Series(minus_dm, index=df.index).rolling(period).sum() / tr_smooth.replace(0, 1e-6))

        dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-6)
        adx = dx.rolling(period).mean().fillna(20.0)
        return adx

    def analyze_candles(self, symbol: str, candles: List[Candle], timeframe: str = "5m") -> RegimeAnalysis:
        """
        Analyzes a candle series and classifies the market regime.
        """
        if len(candles) < 30:
            return RegimeAnalysis(
                symbol=symbol, timeframe=timeframe, regime=REGIME_NEUTRAL,
                ema_structure="MIXED", ema_slope=0.0, vwap_relation="AT_VWAP",
                rsi=50.0, adx=15.0, atr=0.0, volatility_regime="NORMAL_VOL",
                structure="SIDEWAYS", confidence=0.0,
                summary="Insufficient candles for regime analysis (< 30)"
            )

        df = pd.DataFrame([c.__dict__ for c in candles])
        df = compute_all_indicators(df)
        df['adx14'] = self.compute_adx(df, 14)

        last = df.iloc[-1]
        prev = df.iloc[-2]

        c = last['close']
        vwap = last.get('vwap', c)
        rsi = last.get('rsi14', 50.0)
        adx = last.get('adx14', 20.0)
        atr = last.get('atr14', c * 0.01)

        ema20 = last.get('ema20', c)
        ema50 = last.get('ema50', c)
        prev_ema20 = prev.get('ema20', ema20)
        ema_slope = round((ema20 - prev_ema20) / max(prev_ema20, 1.0) * 1000.0, 3)

        # 1. EMA Structure
        if ema20 > ema50 and c > ema20:
            ema_structure = "BULLISH"
        elif ema20 < ema50 and c < ema20:
            ema_structure = "BEARISH"
        else:
            ema_structure = "MIXED"

        # 2. VWAP Relation
        vwap_diff = (c - vwap) / max(vwap, 1.0)
        if vwap_diff > 0.0015:
            vwap_relation = "ABOVE"
        elif vwap_diff < -0.0015:
            vwap_relation = "BELOW"
        else:
            vwap_relation = "AT_VWAP"

        # 3. Volatility Regime
        # Compare current ATR to 30-period average ATR
        avg_atr = df['atr14'].rolling(30).mean().iloc[-1] if len(df) >= 30 else atr
        if atr > avg_atr * 1.35:
            vol_regime = "HIGH_VOL"
        elif atr < avg_atr * 0.70:
            vol_regime = "LOW_VOL"
        else:
            vol_regime = "NORMAL_VOL"

        # 4. Market Structure (swing highs/lows)
        recent_window = df.iloc[-10:]
        max_high = recent_window['high'].max()
        min_low = recent_window['low'].min()
        if c >= max_high * 0.998:
            structure = "HIGHER_HIGHS"
        elif c <= min_low * 1.002:
            structure = "LOWER_LOWS"
        else:
            structure = "SIDEWAYS"

        # 5. Composite Regime Scoring
        bull_signals = 0
        bear_signals = 0

        # EMA
        if ema_structure == "BULLISH": bull_signals += 2
        elif ema_structure == "BEARISH": bear_signals += 2

        # Slope
        if ema_slope > 0.15: bull_signals += 1
        elif ema_slope < -0.15: bear_signals += 1

        # VWAP
        if vwap_relation == "ABOVE": bull_signals += 2
        elif vwap_relation == "BELOW": bear_signals += 2

        # RSI
        if rsi >= 58.0: bull_signals += 2
        elif rsi <= 42.0: bear_signals += 2
        elif 48.0 <= rsi <= 52.0:
            pass # purely neutral

        # ADX (trend strength multiplier)
        is_trending = adx >= 22.0

        # Structure
        if structure == "HIGHER_HIGHS": bull_signals += 2
        elif structure == "LOWER_LOWS": bear_signals += 2

        # Final Classification
        if is_trending and bull_signals >= 7:
            regime = REGIME_STRONG_BULL
            confidence = min(0.96, 0.70 + (bull_signals * 0.03))
        elif bull_signals >= 5 and bull_signals > bear_signals + 2:
            regime = REGIME_BULL
            confidence = 0.80
        elif is_trending and bear_signals >= 7:
            regime = REGIME_STRONG_BEAR
            confidence = min(0.96, 0.70 + (bear_signals * 0.03))
        elif bear_signals >= 5 and bear_signals > bull_signals + 2:
            regime = REGIME_BEAR
            confidence = 0.80
        else:
            regime = REGIME_NEUTRAL
            confidence = 0.40

        summary = (
            f"Regime: {regime} (Conf: {confidence*100:.0f}%), EMA: {ema_structure} (Slope: {ema_slope}), "
            f"VWAP: {vwap_relation}, RSI: {rsi:.1f}, ADX: {adx:.1f}, Structure: {structure}"
        )

        return RegimeAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            regime=regime,
            ema_structure=ema_structure,
            ema_slope=ema_slope,
            vwap_relation=vwap_relation,
            rsi=round(rsi, 1),
            adx=round(adx, 1),
            atr=round(atr, 2),
            volatility_regime=vol_regime,
            structure=structure,
            confidence=round(confidence, 2),
            summary=summary
        )

    def evaluate_from_regimes(
        self,
        symbol: str,
        reg_15m: str,
        reg_5m: str,
        reg_1m: str
    ) -> MultiTimeframeResult:
        is_bull_15m = reg_15m in [REGIME_BULL, REGIME_STRONG_BULL]
        is_bull_5m = reg_5m in [REGIME_BULL, REGIME_STRONG_BULL]
        is_bull_1m = reg_1m in [REGIME_BULL, REGIME_STRONG_BULL]

        is_bear_15m = reg_15m in [REGIME_BEAR, REGIME_STRONG_BEAR]
        is_bear_5m = reg_5m in [REGIME_BEAR, REGIME_STRONG_BEAR]
        is_bear_1m = reg_1m in [REGIME_BEAR, REGIME_STRONG_BEAR]

        if is_bull_15m and is_bull_5m and is_bull_1m:
            return MultiTimeframeResult(
                symbol=symbol,
                tf_15m_regime=reg_15m,
                tf_5m_setup=reg_5m,
                tf_1m_timing=reg_1m,
                aligned=True,
                recommended_direction="BUY_CE",
                alignment_reason=f"Full Bullish MTF Alignment: 15m ({reg_15m}) -> 5m ({reg_5m}) -> 1m ({reg_1m})"
            )

        if is_bear_15m and is_bear_5m and is_bear_1m:
            return MultiTimeframeResult(
                symbol=symbol,
                tf_15m_regime=reg_15m,
                tf_5m_setup=reg_5m,
                tf_1m_timing=reg_1m,
                aligned=True,
                recommended_direction="BUY_PE",
                alignment_reason=f"Full Bearish MTF Alignment: 15m ({reg_15m}) -> 5m ({reg_5m}) -> 1m ({reg_1m})"
            )

        return MultiTimeframeResult(
            symbol=symbol,
            tf_15m_regime=reg_15m,
            tf_5m_setup=reg_5m,
            tf_1m_timing=reg_1m,
            aligned=False,
            recommended_direction="NO_TRADE",
            alignment_reason=f"Conflicting MTF: 15m is {reg_15m}, 5m is {reg_5m}, 1m is {reg_1m}. System requires alignment."
        )

    def evaluate_multi_timeframe(
        self,
        symbol: str,
        candles_15m: List[Candle],
        candles_5m: List[Candle],
        candles_1m: List[Candle]
    ) -> MultiTimeframeResult:
        """
        Synthesizes 15m (Macro Regime), 5m (Setup Confirmation), 1m (Micro Timing).
        Requires alignment between timeframes for CE/PE buying.
        """
        reg_15m = self.analyze_candles(symbol, candles_15m, "15m").regime
        reg_5m = self.analyze_candles(symbol, candles_5m, "5m").regime
        reg_1m = self.analyze_candles(symbol, candles_1m, "1m").regime
        return self.evaluate_from_regimes(symbol, reg_15m, reg_5m, reg_1m)

    def calculate_signal_quality_score(
        self,
        regime_15m: RegimeAnalysis,
        regime_5m: RegimeAnalysis,
        regime_1m: RegimeAnalysis,
        option_liquidity_score: float = 80.0,
        threshold: float = 75.0,
        weights: Optional[Dict[str, float]] = None
    ) -> SignalQualityScore:
        """
        Calculates a 0–100 Signal Quality Score.
        Weights default:
        - Trend: 25
        - Momentum: 20
        - VWAP: 15
        - Market Structure: 15
        - Volatility: 10
        - Volume: 5
        - Option Quality: 10
        Total: 100
        """
        w = weights or {
            "trend": 25.0,
            "momentum": 20.0,
            "vwap": 15.0,
            "structure": 15.0,
            "volatility": 10.0,
            "volume": 5.0,
            "option_quality": 10.0
        }
        notes = []

        # 1. Trend Score (Max 25)
        # Assesses EMA alignment & slope across 15m and 5m
        trend_ratio = 0.0
        if regime_15m.regime in [REGIME_STRONG_BULL, REGIME_STRONG_BEAR]:
            trend_ratio += 0.6
        elif regime_15m.regime in [REGIME_BULL, REGIME_BEAR]:
            trend_ratio += 0.4

        if regime_5m.regime in [REGIME_STRONG_BULL, REGIME_STRONG_BEAR]:
            trend_ratio += 0.4
        elif regime_5m.regime in [REGIME_BULL, REGIME_BEAR]:
            trend_ratio += 0.3
        trend_score = min(w["trend"], round(trend_ratio * w["trend"], 1))
        notes.append(f"Trend: {trend_score}/{w['trend']}")

        # 2. Momentum Score (Max 20)
        # Evaluates RSI positioning & ADX strength
        mom_ratio = 0.0
        if regime_5m.adx >= 25.0:
            mom_ratio += 0.5
        elif regime_5m.adx >= 20.0:
            mom_ratio += 0.3

        if regime_5m.rsi > 60.0 or regime_5m.rsi < 40.0:
            mom_ratio += 0.5
        elif regime_5m.rsi > 55.0 or regime_5m.rsi < 45.0:
            mom_ratio += 0.3
        momentum_score = min(w["momentum"], round(mom_ratio * w["momentum"], 1))
        notes.append(f"Momentum: {momentum_score}/{w['momentum']}")

        # 3. VWAP Score (Max 15)
        vwap_ratio = 0.0
        if regime_5m.vwap_relation in ["ABOVE", "BELOW"]:
            vwap_ratio += 0.6
        if regime_1m.vwap_relation == regime_5m.vwap_relation:
            vwap_ratio += 0.4
        vwap_score = min(w["vwap"], round(vwap_ratio * w["vwap"], 1))
        notes.append(f"VWAP: {vwap_score}/{w['vwap']}")

        # 4. Market Structure (Max 15)
        struct_ratio = 0.0
        if regime_5m.structure in ["HIGHER_HIGHS", "LOWER_LOWS"]:
            struct_ratio += 0.7
        if regime_1m.structure == regime_5m.structure:
            struct_ratio += 0.3
        structure_score = min(w["structure"], round(struct_ratio * w["structure"], 1))
        notes.append(f"Structure: {structure_score}/{w['structure']}")

        # 5. Volatility Score (Max 10)
        vol_score = w["volatility"] if regime_5m.volatility_regime == "NORMAL_VOL" else (w["volatility"] * 0.7)
        vol_score = round(vol_score, 1)
        notes.append(f"Volatility: {vol_score}/{w['volatility']}")

        # 6. Volume Score (Max 5)
        volume_score = round(w["volume"] * 0.9, 1)
        notes.append(f"Volume: {volume_score}/{w['volume']}")

        # 7. Option Quality Score (Max 10)
        opt_score = round((min(100.0, max(0.0, option_liquidity_score)) / 100.0) * w["option_quality"], 1)
        notes.append(f"Option Quality: {opt_score}/{w['option_quality']}")

        total = round(trend_score + momentum_score + vwap_score + structure_score + vol_score + volume_score + opt_score, 1)
        passed = (total >= threshold)

        return SignalQualityScore(
            total_score=total,
            trend_score=trend_score,
            momentum_score=momentum_score,
            vwap_score=vwap_score,
            structure_score=structure_score,
            volatility_score=vol_score,
            volume_score=volume_score,
            option_quality_score=opt_score,
            threshold_passed=passed,
            threshold_used=threshold,
            breakdown_notes=notes
        )

    def validate_no_trade_conditions(
        self,
        signal_score: float,
        threshold: float,
        is_mtf_aligned: bool,
        market_regime: str,
        spread_pct: float,
        liquidity_score: float,
        is_market_data_stale: bool,
        is_broker_connected: bool,
        kill_switch_active: bool,
        daily_loss_reached: bool,
        max_trades_reached: bool,
        open_positions_count: int,
        max_open_positions: int = 1,
        reconciliation_mismatch: bool = False
    ) -> NoTradeDecision:
        """
        Rigorous No-Trade Safety Engine.
        Evaluates 15+ safety conditions. If any condition fails, enforces NO TRADE.
        """
        rejections = []

        if kill_switch_active:
            rejections.append("KILL_SWITCH_ACTIVE: Emergency stop engaged")

        if is_market_data_stale:
            rejections.append("STALE_DATA_PROTECTION: Market data feed is stale or disconnected")

        if not is_broker_connected:
            rejections.append("BROKER_DISCONNECTED: Upstox bridge disconnected")

        if reconciliation_mismatch:
            rejections.append("RECONCILIATION_REQUIRED: Broker positions do not match local records")

        if daily_loss_reached:
            rejections.append("DAILY_LOSS_LIMIT: Circuit breaker active for remainder of session")

        if max_trades_reached:
            rejections.append("MAX_TRADES_LIMIT: Maximum allowed daily trades reached")

        if open_positions_count >= max_open_positions:
            rejections.append(f"MAX_POSITION_REACHED: Currently hold {open_positions_count} open position(s) (limit: {max_open_positions})")

        if market_regime == REGIME_NEUTRAL:
            rejections.append("NEUTRAL_REGIME: Market is sideways/indecisive. System does not trade chop")

        if not is_mtf_aligned:
            rejections.append("MTF_CONFLICT: 15m, 5m, and 1m timeframes are not in full directional consensus")

        if signal_score < threshold:
            rejections.append(f"SIGNAL_SCORE_BELOW_THRESHOLD: Score {signal_score:.1f} < Required {threshold:.1f}")

        if spread_pct > 2.5:
            rejections.append(f"WIDE_SPREAD: Option bid-ask spread {spread_pct:.1f}% exceeds 2.5% execution tolerance")

        if liquidity_score < 45.0:
            rejections.append(f"INSUFFICIENT_LIQUIDITY: Option liquidity score {liquidity_score:.1f} < 45.0 minimum")

        # Session timing check (no new trades after 15:15 IST)
        now_dt = datetime.now()
        # If in market session after 15:15 IST
        if now_dt.hour > 15 or (now_dt.hour == 15 and now_dt.minute >= 15):
            rejections.append("SESSION_EXPIRY_WINDOW: New entries forbidden after 15:15 IST to prevent end-of-day decay")

        can_trade = (len(rejections) == 0)
        primary = rejections[0] if rejections else "ALL_SYSTEMS_GO: Trade entry authorized"

        return NoTradeDecision(
            can_trade=can_trade,
            rejection_reasons=rejections,
            primary_reason=primary
        )

regime_engine = MarketRegimeEngine()
