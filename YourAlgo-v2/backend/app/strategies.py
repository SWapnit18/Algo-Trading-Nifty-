"""
YOURALGO - Production Index Options Strategy Architecture
Dedicated exclusively to Indian Index Derivatives: NIFTY 50 & BANK NIFTY (CE/PE Buying Only).
Forbidden: Short options, naked selling, futures, individual stocks.

Implements:
1. Strategy 1: FIXED RR 1:3 (Index Options Buyer)
2. Strategy 2: ADAPTIVE TREND RIDER (Multi-layer decision, dynamic trailing, thesis exit)
3. Strategy 3: VOLATILITY SQUEEZE BREAKOUT (Bollinger/Keltner squeeze expansion)
4. Strategy 4: OPENING RANGE BREAKOUT (15m ORB with Volume expansion)
5. Strategy 5: MEAN REVERSION EXTREME (2.2 ATR stretch + RSI exhaustion)
"""

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime
import pandas as pd
import numpy as np
import logging

from .market_data import Candle
from .indicators import compute_all_indicators
from .options_engine import options_engine, SelectedContract
from .regime_engine import (
    regime_engine,
    REGIME_STRONG_BULL, REGIME_BULL, REGIME_NEUTRAL, REGIME_BEAR, REGIME_STRONG_BEAR
)

logger = logging.getLogger(__name__)

@dataclass
class OptionSignalResult:
    signal_id: str
    underlying: str              # NIFTY or BANKNIFTY
    strategy_code: str
    strategy_name: str
    strategy_version: str
    direction: str               # BUY_CE, BUY_PE, NO_TRADE
    underlying_price: float
    option_contract: Optional[Dict[str, Any]]
    option_symbol: str
    entry_price: float           # Estimated option premium entry
    stop_loss: float             # Option premium stop loss
    target: float                # Option premium target (0.0 for trailing strategies)
    trailing_type: str           # NONE, ATR_TRAILING, SWING_TRAILING, THESIS_TRAILING
    quantity: int                # In lots * lot_size
    lots: int
    risk_amount: float           # Max rupee risk (Capital * Risk %)
    risk_reward: float
    signal_score: float          # 0 to 100
    market_regime: str
    timeframe_alignment: bool
    confidence: float
    timestamp: str
    reason: str
    thesis_exit_conditions: List[str]

class BaseOptionStrategy:
    code = "BASE"
    name = "Base Index Options Strategy"
    version = "1.0.0"
    description = ""
    parameters: Dict[str, Any] = {}

    def evaluate(
        self,
        underlying: str,
        candles_15m: List[Candle],
        candles_5m: List[Candle],
        candles_1m: List[Candle],
        capital: float = 100000.0,
        risk_pct: float = 0.01,
        params: Optional[Dict[str, Any]] = None
    ) -> OptionSignalResult:
        raise NotImplementedError

# =====================================================================
# STRATEGY 1: FIXED RR 1:3 (Index Options Buyer)
# =====================================================================
class StrategyFixedRR13(BaseOptionStrategy):
    """
    Strategy 1: FIXED RR 1:3 (Index Options Buying)
    Evaluates NIFTY/BANKNIFTY trend via EMA and VWAP.
    If Bullish -> Buys optimal CE option.
    If Bearish -> Buys optimal PE option.
    Stop Loss: 1.5 * Option ATR (or 15-20% premium limit).
    Target: Exactly 3.0 * Risk Distance (Fixed 1:3 RR).
    Monitors until Target or Stop Loss hit.
    """
    code = "STRAT_FIXED_RR_13"
    name = "Fixed RR 1:3 (Index Options)"
    version = "2.1.0"
    description = "Deterministic trend follower entering ATM CE/PE with dynamic 1% risk and fixed 1:3 profit target."
    parameters = {
        "risk_reward": 3.0,
        "atr_stop_multiplier": 1.5,
        "rsi_long_threshold": 52.0,
        "rsi_short_threshold": 48.0,
        "max_premium_risk_pct": 0.25
    }

    def evaluate(
        self,
        underlying: str,
        candles_15m: List[Candle],
        candles_5m: List[Candle],
        candles_1m: List[Candle],
        capital: float = 100000.0,
        risk_pct: float = 0.01,
        params: Optional[Dict[str, Any]] = None
    ) -> OptionSignalResult:
        sig_id = f"sig_13_{uuid.uuid4().hex[:8]}"
        now_str = datetime.utcnow().isoformat()
        p = {**self.parameters, **(params or {})}

        if len(candles_5m) < 40:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=0.0,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=p["risk_reward"],
                signal_score=0.0, market_regime=REGIME_NEUTRAL, timeframe_alignment=False,
                confidence=0.0, timestamp=now_str, reason="Insufficient candles (< 40)",
                thesis_exit_conditions=[]
            )

        df = pd.DataFrame([c.__dict__ for c in candles_5m])
        df = compute_all_indicators(df)
        last = df.iloc[-1]

        spot = last['close']
        ema20 = last.get('ema20', spot)
        ema50 = last.get('ema50', spot)
        vwap = last.get('vwap', spot)
        rsi = last.get('rsi14', 50.0)
        atr = last.get('atr14', spot * 0.008)

        is_bullish = (ema20 > ema50) and (spot > vwap) and (rsi >= p["rsi_long_threshold"])
        is_bearish = (ema20 < ema50) and (spot < vwap) and (rsi <= p["rsi_short_threshold"])

        if is_bullish:
            direction = "BUY_CE"
            regime = REGIME_BULL
        elif is_bearish:
            direction = "BUY_PE"
            regime = REGIME_BEAR
        else:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=p["risk_reward"],
                signal_score=45.0, market_regime=REGIME_NEUTRAL, timeframe_alignment=False,
                confidence=0.0, timestamp=now_str,
                reason=f"No 1:3 setup on {underlying}: Spot ₹{spot:.1f}, EMA20/50: {ema20:.1f}/{ema50:.1f}, VWAP: {vwap:.1f}, RSI: {rsi:.1f}",
                thesis_exit_conditions=[]
            )

        # Select optimal contract
        contract = options_engine.select_best_option(underlying, direction, spot)
        if not contract:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=p["risk_reward"],
                signal_score=50.0, market_regime=regime, timeframe_alignment=True,
                confidence=0.0, timestamp=now_str,
                reason="Failed to find liquid option contract meeting quality standards",
                thesis_exit_conditions=[]
            )

        opt_entry = contract.ltp
        # Option stop distance in ₹ premium
        delta_abs = max(0.35, abs(contract.delta))
        raw_stop_dist = max(5.0, (atr * delta_abs * p["atr_stop_multiplier"]))
        # Cap stop loss to max percentage of premium
        max_premium_risk = opt_entry * p["max_premium_risk_pct"]
        opt_stop_dist = round(min(raw_stop_dist, max_premium_risk), 2)
        opt_sl = round(max(0.50, opt_entry - opt_stop_dist), 2)
        opt_target = round(opt_entry + (opt_stop_dist * p["risk_reward"]), 2)

        # Capital & Lot Sizing
        total_risk_allowed = capital * risk_pct
        lot_size = contract.lot_size
        risk_per_lot = opt_stop_dist * lot_size
        lots = max(1, int(total_risk_allowed // max(risk_per_lot, 1.0)))
        qty = lots * lot_size
        actual_risk = round(lots * risk_per_lot, 2)

        return OptionSignalResult(
            signal_id=sig_id,
            underlying=underlying,
            strategy_code=self.code,
            strategy_name=self.name,
            strategy_version=self.version,
            direction=direction,
            underlying_price=round(spot, 2),
            option_contract=asdict(contract),
            option_symbol=contract.symbol,
            entry_price=opt_entry,
            stop_loss=opt_sl,
            target=opt_target,
            trailing_type="NONE",
            quantity=qty,
            lots=lots,
            risk_amount=actual_risk,
            risk_reward=p["risk_reward"],
            signal_score=78.5,
            market_regime=regime,
            timeframe_alignment=True,
            confidence=0.85,
            timestamp=now_str,
            reason=f"1:3 Setup on {underlying} ({direction}): {contract.selection_reason}. Entry ₹{opt_entry}, SL ₹{opt_sl}, Target ₹{opt_target} (3R)",
            thesis_exit_conditions=["HIT_TARGET", "HIT_HARD_SL", "SESSION_CLOSE_1515"]
        )

# =====================================================================
# STRATEGY 2: ADAPTIVE TREND RIDER (Advanced Multi-Layer Decision Engine)
# =====================================================================
class StrategyAdaptiveTrendRider(BaseOptionStrategy):
    """
    Strategy 2: ADAPTIVE TREND RIDER (Advanced Options Buying Engine)
    Multi-layer decision pipeline:
    - Data Quality Gate
    - Market Regime Engine (STRONG_BULL -> BUY CE, STRONG_BEAR -> BUY PE, NEUTRAL -> NO TRADE)
    - Multi-Timeframe Alignment (15m Macro + 5m Setup + 1m Micro Timing)
    - Signal Quality Scoring (must exceed threshold: 75.0)
    - Option Quality Engine (optimal delta, tightest spread, high liquidity)
    - Adaptive Stop Loss (ATR + Swing hybrid)
    - Adaptive Trailing Stop: Initial Stop -> Breakeven at 1.5R -> Profit Lock at 2.0R -> Trailing Stop
    - Thesis Exit Engine: Exits early if VWAP lost or momentum reverses
    - No fixed target: rides full trend extension
    """
    code = "STRAT_ADAPTIVE_TREND_RIDER"
    name = "Adaptive Trend Rider (Multi-Layer)"
    version = "2.4.0"
    description = "Institutional multi-layer decision pipeline with multi-timeframe alignment, adaptive trailing, and thesis exit."
    parameters = {
        "score_threshold": 75.0,
        "breakeven_trigger_r": 1.5,
        "profit_lock_r": 2.0,
        "atr_trail_multiplier": 1.8,
        "thesis_exit_on_vwap_cross": True,
        "thesis_exit_on_adx_drop": True,
        "time_exit_stalled_bars": 12,
        "max_risk_pct": 0.015
    }

    def evaluate(
        self,
        underlying: str,
        candles_15m: List[Candle],
        candles_5m: List[Candle],
        candles_1m: List[Candle],
        capital: float = 100000.0,
        risk_pct: float = 0.01,
        params: Optional[Dict[str, Any]] = None
    ) -> OptionSignalResult:
        sig_id = f"sig_atr_{uuid.uuid4().hex[:8]}"
        now_str = datetime.utcnow().isoformat()
        p = {**self.parameters, **(params or {})}

        # 1. Multi-Timeframe Alignment Evaluation
        mtf_result = regime_engine.evaluate_multi_timeframe(
            underlying, candles_15m, candles_5m, candles_1m
        )
        if not mtf_result.aligned or mtf_result.recommended_direction == "NO_TRADE":
            spot = candles_5m[-1].close if candles_5m else 0.0
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="ATR_TRAILING", quantity=0, lots=0, risk_amount=0.0, risk_reward=0.0,
                signal_score=40.0, market_regime=mtf_result.tf_15m_regime, timeframe_alignment=False,
                confidence=0.0, timestamp=now_str,
                reason=mtf_result.alignment_reason,
                thesis_exit_conditions=[]
            )

        # 2. Regime and Signal Quality Scoring
        reg_15m = regime_engine.analyze_candles(underlying, candles_15m, "15m")
        reg_5m = regime_engine.analyze_candles(underlying, candles_5m, "5m")
        reg_1m = regime_engine.analyze_candles(underlying, candles_1m, "1m")

        spot = reg_5m.atr + candles_5m[-1].close if candles_5m else 25000.0
        spot = round(candles_5m[-1].close, 2)

        # 3. Dynamic Option Contract Selection
        direction = mtf_result.recommended_direction
        contract = options_engine.select_best_option(underlying, direction, spot)
        if not contract:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="ATR_TRAILING", quantity=0, lots=0, risk_amount=0.0, risk_reward=0.0,
                signal_score=50.0, market_regime=reg_5m.regime, timeframe_alignment=True,
                confidence=0.0, timestamp=now_str,
                reason="Option Quality Gate rejected: No contract meeting delta & spread limits",
                thesis_exit_conditions=[]
            )

        # 4. Composite 0-100 Signal Quality Score
        score_obj = regime_engine.calculate_signal_quality_score(
            reg_15m, reg_5m, reg_1m,
            option_liquidity_score=contract.liquidity_score,
            threshold=p["score_threshold"]
        )

        if not score_obj.threshold_passed:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=asdict(contract), option_symbol=contract.symbol,
                entry_price=0.0, stop_loss=0.0, target=0.0, trailing_type="ATR_TRAILING",
                quantity=0, lots=0, risk_amount=0.0, risk_reward=0.0,
                signal_score=score_obj.total_score, market_regime=reg_5m.regime,
                timeframe_alignment=True, confidence=0.0, timestamp=now_str,
                reason=f"Signal Quality Score {score_obj.total_score:.1f} < Threshold {score_obj.threshold_used:.1f}. Breakdown: {', '.join(score_obj.breakdown_notes)}",
                thesis_exit_conditions=[]
            )

        # 5. Adaptive Stop Loss & Sizing
        opt_entry = contract.ltp
        delta_abs = max(0.40, abs(contract.delta))
        raw_stop_dist = max(6.0, reg_5m.atr * delta_abs * 1.4)
        max_prem_stop = opt_entry * 0.22
        opt_stop_dist = round(min(raw_stop_dist, max_prem_stop), 2)
        opt_sl = round(max(0.50, opt_entry - opt_stop_dist), 2)

        # In Adaptive Trend Rider, Target is 0.0 because it trails adaptively!
        opt_target = 0.0

        # Position Sizing
        total_risk_allowed = capital * min(risk_pct, p["max_risk_pct"])
        risk_per_lot = opt_stop_dist * contract.lot_size
        lots = max(1, int(total_risk_allowed // max(risk_per_lot, 1.0)))
        qty = lots * contract.lot_size
        actual_risk = round(lots * risk_per_lot, 2)

        thesis_conditions = [
            f"VWAP_REVERSAL: Underlying cross back across VWAP ({reg_5m.vwap_relation})",
            "MOMENTUM_EXHAUSTION: ADX drop below 18 or RSI divergence",
            "REGIME_DETERIORATION: 15m regime flips to NEUTRAL or opposing",
            "TIME_DECAY_EXIT: Position non-progressive for 12 consecutive 5m bars",
            "SESSION_CLOSE_1515: Mandatory end-of-day square-off at 15:15 IST"
        ]

        return OptionSignalResult(
            signal_id=sig_id,
            underlying=underlying,
            strategy_code=self.code,
            strategy_name=self.name,
            strategy_version=self.version,
            direction=direction,
            underlying_price=spot,
            option_contract=asdict(contract),
            option_symbol=contract.symbol,
            entry_price=opt_entry,
            stop_loss=opt_sl,
            target=opt_target,
            trailing_type="ATR_TRAILING",
            quantity=qty,
            lots=lots,
            risk_amount=actual_risk,
            risk_reward=0.0, # Pure trailing
            signal_score=score_obj.total_score,
            market_regime=reg_5m.regime,
            timeframe_alignment=True,
            confidence=round(score_obj.total_score / 100.0, 2),
            timestamp=now_str,
            reason=f"Adaptive Trend Signal (Score: {score_obj.total_score:.1f}/100): 15m/5m/1m {direction}. {contract.selection_reason}. Trailing: Breakeven @ 1.5R, Lock @ 2.0R",
            thesis_exit_conditions=thesis_conditions
        )

# =====================================================================
# STRATEGY 3: VOLATILITY SQUEEZE BREAKOUT (Index Options Buying)
# =====================================================================
class StrategyVolatilitySqueeze(BaseOptionStrategy):
    """
    Strategy 3: VOLATILITY SQUEEZE BREAKOUT (John Carter Squeeze Adaptation)
    Detects Bollinger Bands (20, 2.0) contracting inside Keltner Channel (20, 1.5 ATR).
    When the squeeze 'fires' out of compression:
    - If Momentum Oscillator > 0 & Close > VWAP -> BUY ATM CE.
    - If Momentum Oscillator < 0 & Close < VWAP -> BUY ATM PE.
    Exploits sudden volatility expansion in index options.
    """
    code = "STRAT_VOLATILITY_SQUEEZE"
    name = "Volatility Squeeze Breakout"
    version = "1.5.0"
    description = "Bollinger Bands inside Keltner Channel compression breakout with momentum acceleration."
    parameters = {
        "bb_length": 20,
        "bb_mult": 2.0,
        "kc_mult": 1.5,
        "adx_threshold": 22.0,
        "risk_reward": 2.5
    }

    def evaluate(
        self,
        underlying: str,
        candles_15m: List[Candle],
        candles_5m: List[Candle],
        candles_1m: List[Candle],
        capital: float = 100000.0,
        risk_pct: float = 0.01,
        params: Optional[Dict[str, Any]] = None
    ) -> OptionSignalResult:
        sig_id = f"sig_sqz_{uuid.uuid4().hex[:8]}"
        now_str = datetime.utcnow().isoformat()
        p = {**self.parameters, **(params or {})}

        if len(candles_5m) < 40:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=0.0,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="ATR_TRAILING", quantity=0, lots=0, risk_amount=0.0, risk_reward=2.5,
                signal_score=0.0, market_regime=REGIME_NEUTRAL, timeframe_alignment=False,
                confidence=0.0, timestamp=now_str, reason="Insufficient candles",
                thesis_exit_conditions=[]
            )

        df = pd.DataFrame([c.__dict__ for c in candles_5m])
        df = compute_all_indicators(df)
        df['adx14'] = regime_engine.compute_adx(df, 14)

        # Squeeze indicator logic: BB vs Keltner
        c = df['close']
        sma20 = c.rolling(p["bb_length"]).mean()
        std20 = c.rolling(p["bb_length"]).std()
        bb_upper = sma20 + (p["bb_mult"] * std20)
        bb_lower = sma20 - (p["bb_mult"] * std20)

        atr = df['atr14']
        kc_upper = sma20 + (p["kc_mult"] * atr)
        kc_lower = sma20 - (p["kc_mult"] * atr)

        # Squeeze is on when BB is inside KC
        squeeze_on = (bb_lower > kc_lower) & (bb_upper < kc_upper)
        was_squeezing = squeeze_on.iloc[-3:-1].any()
        squeeze_fired = (not squeeze_on.iloc[-1]) and was_squeezing

        last = df.iloc[-1]
        spot = last['close']
        vwap = last.get('vwap', spot)
        adx = last.get('adx14', 20.0)

        # Linear regression momentum
        mom = spot - sma20.iloc[-1]

        if squeeze_fired and adx >= p["adx_threshold"] and mom > 0 and spot > vwap:
            direction = "BUY_CE"
            regime = REGIME_STRONG_BULL
            reason_txt = f"Squeeze Fired Bullish on {underlying}: BB expanded out of KC with positive momentum (+{mom:.1f}) & ADX {adx:.1f}"
        elif squeeze_fired and adx >= p["adx_threshold"] and mom < 0 and spot < vwap:
            direction = "BUY_PE"
            regime = REGIME_STRONG_BEAR
            reason_txt = f"Squeeze Fired Bearish on {underlying}: BB expanded out of KC with negative momentum ({mom:.1f}) & ADX {adx:.1f}"
        else:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="ATR_TRAILING", quantity=0, lots=0, risk_amount=0.0, risk_reward=2.5,
                signal_score=45.0, market_regime=REGIME_NEUTRAL, timeframe_alignment=False,
                confidence=0.0, timestamp=now_str,
                reason=f"No Volatility Squeeze firing on {underlying} (Squeeze State: {'ACTIVE' if squeeze_on.iloc[-1] else 'OFF'}, ADX: {adx:.1f})",
                thesis_exit_conditions=[]
            )

        contract = options_engine.select_best_option(underlying, direction, spot)
        if not contract:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="ATR_TRAILING", quantity=0, lots=0, risk_amount=0.0, risk_reward=2.5,
                signal_score=50.0, market_regime=regime, timeframe_alignment=True,
                confidence=0.0, timestamp=now_str, reason="Contract selection failed",
                thesis_exit_conditions=[]
            )

        opt_entry = contract.ltp
        delta_abs = max(0.40, abs(contract.delta))
        opt_stop_dist = max(5.0, round(atr.iloc[-1] * delta_abs * 1.3, 2))
        opt_sl = round(max(0.50, opt_entry - opt_stop_dist), 2)
        opt_target = round(opt_entry + (opt_stop_dist * p["risk_reward"]), 2)

        total_risk = capital * risk_pct
        risk_per_lot = opt_stop_dist * contract.lot_size
        lots = max(1, int(total_risk // max(risk_per_lot, 1.0)))
        qty = lots * contract.lot_size

        return OptionSignalResult(
            signal_id=sig_id,
            underlying=underlying,
            strategy_code=self.code,
            strategy_name=self.name,
            strategy_version=self.version,
            direction=direction,
            underlying_price=spot,
            option_contract=asdict(contract),
            option_symbol=contract.symbol,
            entry_price=opt_entry,
            stop_loss=opt_sl,
            target=opt_target,
            trailing_type="ATR_TRAILING",
            quantity=qty,
            lots=lots,
            risk_amount=round(lots * risk_per_lot, 2),
            risk_reward=p["risk_reward"],
            signal_score=84.0,
            market_regime=regime,
            timeframe_alignment=True,
            confidence=0.88,
            timestamp=now_str,
            reason=reason_txt,
            thesis_exit_conditions=["MOMENTUM_CROSSOVER", "BOLLINGER_RE_CONTRACTION", "SESSION_CLOSE_1515"]
        )

# =====================================================================
# STRATEGY 4: OPENING RANGE BREAKOUT (15m ORB Index Options)
# =====================================================================
class StrategyOpeningRangeBreakout(BaseOptionStrategy):
    """
    Strategy 4: OPENING RANGE BREAKOUT (15m ORB for NIFTY & BANKNIFTY)
    Calculates the 15-minute Opening Range (09:15 to 09:30 IST).
    Fires on high volume breakout with VWAP alignment:
    - Close > OR High & RVOL >= 1.2 -> BUY ATM CE.
    - Close < OR Low & RVOL >= 1.2 -> BUY ATM PE.
    Target: 1:3 RR.
    """
    code = "STRAT_ORB_INDEX"
    name = "Opening Range Breakout (15m)"
    version = "1.8.0"
    description = "15-minute opening range breakout with volume surge confirmation for high-momentum index options."
    parameters = {
        "or_bars": 15,
        "rvol_min": 1.2,
        "risk_reward": 3.0
    }

    def evaluate(
        self,
        underlying: str,
        candles_15m: List[Candle],
        candles_5m: List[Candle],
        candles_1m: List[Candle],
        capital: float = 100000.0,
        risk_pct: float = 0.01,
        params: Optional[Dict[str, Any]] = None
    ) -> OptionSignalResult:
        sig_id = f"sig_orb_{uuid.uuid4().hex[:8]}"
        now_str = datetime.utcnow().isoformat()
        p = {**self.parameters, **(params or {})}

        if len(candles_5m) < 20:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=0.0,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=3.0,
                signal_score=0.0, market_regime=REGIME_NEUTRAL, timeframe_alignment=False,
                confidence=0.0, timestamp=now_str, reason="Insufficient candles for ORB",
                thesis_exit_conditions=[]
            )

        df = pd.DataFrame([c.__dict__ for c in candles_5m])
        df = compute_all_indicators(df)

        or_window = df.iloc[-18:-3] if len(df) >= 18 else df.iloc[:-1]
        or_high = or_window['high'].max()
        or_low = or_window['low'].min()

        last = df.iloc[-1]
        spot = last['close']
        vwap = last.get('vwap', spot)
        rvol = last.get('rvol', 1.0)
        atr = last.get('atr14', spot * 0.008)

        if spot > or_high and rvol >= p["rvol_min"] and spot > vwap:
            direction = "BUY_CE"
            regime = REGIME_STRONG_BULL
            reason_txt = f"ORB Bullish Breakout on {underlying}: Close ₹{spot:.1f} > OR High ₹{or_high:.1f} with RVOL {rvol:.2f}"
        elif spot < or_low and rvol >= p["rvol_min"] and spot < vwap:
            direction = "BUY_PE"
            regime = REGIME_STRONG_BEAR
            reason_txt = f"ORB Bearish Breakdown on {underlying}: Close ₹{spot:.1f} < OR Low ₹{or_low:.1f} with RVOL {rvol:.2f}"
        else:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=3.0,
                signal_score=40.0, market_regime=REGIME_NEUTRAL, timeframe_alignment=False,
                confidence=0.0, timestamp=now_str,
                reason=f"No ORB breakout on {underlying}: Spot {spot:.1f} inside [{or_low:.1f} - {or_high:.1f}]",
                thesis_exit_conditions=[]
            )

        contract = options_engine.select_best_option(underlying, direction, spot)
        if not contract:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=3.0,
                signal_score=50.0, market_regime=regime, timeframe_alignment=True,
                confidence=0.0, timestamp=now_str, reason="Contract selection failed",
                thesis_exit_conditions=[]
            )

        opt_entry = contract.ltp
        delta_abs = max(0.40, abs(contract.delta))
        opt_stop_dist = max(5.0, round(atr * delta_abs * 1.5, 2))
        opt_sl = round(max(0.50, opt_entry - opt_stop_dist), 2)
        opt_target = round(opt_entry + (opt_stop_dist * p["risk_reward"]), 2)

        total_risk = capital * risk_pct
        risk_per_lot = opt_stop_dist * contract.lot_size
        lots = max(1, int(total_risk // max(risk_per_lot, 1.0)))
        qty = lots * contract.lot_size

        return OptionSignalResult(
            signal_id=sig_id,
            underlying=underlying,
            strategy_code=self.code,
            strategy_name=self.name,
            strategy_version=self.version,
            direction=direction,
            underlying_price=spot,
            option_contract=asdict(contract),
            option_symbol=contract.symbol,
            entry_price=opt_entry,
            stop_loss=opt_sl,
            target=opt_target,
            trailing_type="NONE",
            quantity=qty,
            lots=lots,
            risk_amount=round(lots * risk_per_lot, 2),
            risk_reward=p["risk_reward"],
            signal_score=81.0,
            market_regime=regime,
            timeframe_alignment=True,
            confidence=0.86,
            timestamp=now_str,
            reason=reason_txt,
            thesis_exit_conditions=["HIT_TARGET", "HIT_HARD_SL", "SESSION_CLOSE_1515"]
        )

# =====================================================================
# STRATEGY 5: MEAN REVERSION EXTREME (Index Options Buying)
# =====================================================================
class StrategyMeanReversionExtreme(BaseOptionStrategy):
    """
    Strategy 5: MEAN REVERSION EXTREME (Index Options Buying)
    Capitalizes on extreme exhaustion stretches from VWAP (>= 2.2 * ATR):
    - Oversold: Spot is <= VWAP - (2.2 * ATR) AND RSI < 25 -> BUY ATM CE for snapback.
    - Overbought: Spot is >= VWAP + (2.2 * ATR) AND RSI > 75 -> BUY ATM PE for snapback.
    Quick target at VWAP with tight 1:2.5 RR.
    """
    code = "STRAT_MEAN_REVERSION_EXTREME"
    name = "Mean Reversion Extreme (Exhaustion)"
    version = "1.2.0"
    description = "Statistical VWAP exhaustion bounce capitalizing on 2.2+ ATR stretch with extreme RSI."
    parameters = {
        "vwap_atr_mult": 2.2,
        "rsi_oversold": 28.0,
        "rsi_overbought": 72.0,
        "risk_reward": 2.5
    }

    def evaluate(
        self,
        underlying: str,
        candles_15m: List[Candle],
        candles_5m: List[Candle],
        candles_1m: List[Candle],
        capital: float = 100000.0,
        risk_pct: float = 0.01,
        params: Optional[Dict[str, Any]] = None
    ) -> OptionSignalResult:
        sig_id = f"sig_mr_{uuid.uuid4().hex[:8]}"
        now_str = datetime.utcnow().isoformat()
        p = {**self.parameters, **(params or {})}

        if len(candles_5m) < 40:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=0.0,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=2.5,
                signal_score=0.0, market_regime=REGIME_NEUTRAL, timeframe_alignment=False,
                confidence=0.0, timestamp=now_str, reason="Insufficient candles",
                thesis_exit_conditions=[]
            )

        df = pd.DataFrame([c.__dict__ for c in candles_5m])
        df = compute_all_indicators(df)
        last = df.iloc[-1]
        spot = last['close']
        vwap = last.get('vwap', spot)
        rsi = last.get('rsi14', 50.0)
        atr = last.get('atr14', spot * 0.008)

        lower_exhaustion = vwap - (p["vwap_atr_mult"] * atr)
        upper_exhaustion = vwap + (p["vwap_atr_mult"] * atr)

        if spot <= lower_exhaustion and rsi <= p["rsi_oversold"]:
            direction = "BUY_CE"
            regime = REGIME_STRONG_BEAR # Market was dumping, entering counter-trend snapback
            reason_txt = f"Mean Reversion Oversold Bounce on {underlying}: Spot ₹{spot:.1f} extended 2.2 ATR below VWAP ({vwap:.1f}), RSI {rsi:.1f}"
        elif spot >= upper_exhaustion and rsi >= p["rsi_overbought"]:
            direction = "BUY_PE"
            regime = REGIME_STRONG_BULL # Market was pumping, entering counter-trend snapback
            reason_txt = f"Mean Reversion Overbought Fade on {underlying}: Spot ₹{spot:.1f} extended 2.2 ATR above VWAP ({vwap:.1f}), RSI {rsi:.1f}"
        else:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=2.5,
                signal_score=35.0, market_regime=REGIME_NEUTRAL, timeframe_alignment=False,
                confidence=0.0, timestamp=now_str,
                reason=f"Spot {spot:.1f} within normal VWAP envelope [{lower_exhaustion:.1f} - {upper_exhaustion:.1f}]",
                thesis_exit_conditions=[]
            )

        contract = options_engine.select_best_option(underlying, direction, spot)
        if not contract:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=2.5,
                signal_score=50.0, market_regime=regime, timeframe_alignment=True,
                confidence=0.0, timestamp=now_str, reason="Contract selection failed",
                thesis_exit_conditions=[]
            )

        opt_entry = contract.ltp
        delta_abs = max(0.40, abs(contract.delta))
        opt_stop_dist = max(5.0, round(atr * delta_abs * 1.2, 2))
        opt_sl = round(max(0.50, opt_entry - opt_stop_dist), 2)
        opt_target = round(opt_entry + (opt_stop_dist * p["risk_reward"]), 2)

        total_risk = capital * risk_pct
        risk_per_lot = opt_stop_dist * contract.lot_size
        lots = max(1, int(total_risk // max(risk_per_lot, 1.0)))
        qty = lots * contract.lot_size

        return OptionSignalResult(
            signal_id=sig_id,
            underlying=underlying,
            strategy_code=self.code,
            strategy_name=self.name,
            strategy_version=self.version,
            direction=direction,
            underlying_price=spot,
            option_contract=asdict(contract),
            option_symbol=contract.symbol,
            entry_price=opt_entry,
            stop_loss=opt_sl,
            target=opt_target,
            trailing_type="NONE",
            quantity=qty,
            lots=lots,
            risk_amount=round(lots * risk_per_lot, 2),
            risk_reward=p["risk_reward"],
            signal_score=77.0,
            market_regime=regime,
            timeframe_alignment=True,
            confidence=0.80,
            timestamp=now_str,
            reason=reason_txt,
            thesis_exit_conditions=["HIT_TARGET", "HIT_HARD_SL", "SESSION_CLOSE_1515"]
        )

# =====================================================================
# STRATEGY 6: EXPIRY DAY GAMMA SCALPER (Index Options Buyer)
# =====================================================================
class StrategyExpiryGammaScalper(BaseOptionStrategy):
    """
    Strategy 6: EXPIRY DAY GAMMA SCALPER (Index Options Buying)
    Engineered for rapid gamma expansion on Expiry Days or high momentum breakouts.
    Triggers when spot price pierces the rolling session Day High or Day Low with
    an aggressive volume expansion (> 1.75x 20-bar avg) and trending ADX.
    Enters near-ATM / slight OTM CE/PE with tight SL and fast 1:3.5 profit target.
    """
    code = "STRAT_EXPIRY_GAMMA_SCALPER"
    name = "Expiry Day Gamma Scalper"
    version = "1.0.0"
    description = "Intraday gamma surge engine entering near-ATM options on high-volume session range breakouts with tight trailing."
    parameters = {
        "min_volume_mult": 1.30,
        "min_adx": 18.0,
        "target_rr": 3.0,
        "atr_stop_multiplier": 1.25,
        "lookback_bars": 15,
        "max_premium_risk_pct": 0.25
    }

    def evaluate(
        self,
        underlying: str,
        candles_15m: List[Candle],
        candles_5m: List[Candle],
        candles_1m: List[Candle],
        capital: float = 100000.0,
        risk_pct: float = 0.01,
        params: Optional[Dict[str, Any]] = None
    ) -> OptionSignalResult:
        sig_id = f"sig_gamma_{uuid.uuid4().hex[:8]}"
        now_str = datetime.utcnow().isoformat()
        p = {**self.parameters, **(params or {})}

        if len(candles_5m) < p["lookback_bars"] + 10:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=0.0,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=p["target_rr"],
                signal_score=0.0, market_regime=REGIME_NEUTRAL, timeframe_alignment=False,
                confidence=0.0, timestamp=now_str, reason="Insufficient 5m candles",
                thesis_exit_conditions=[]
            )

        df = pd.DataFrame([c.__dict__ for c in candles_5m])
        df = compute_all_indicators(df)
        last = df.iloc[-1]
        spot = last['close']
        atr = last.get('atr14', spot * 0.007)
        adx = last.get('adx', 20.0)

        lookback = min(p["lookback_bars"], max(5, len(df) - 2))
        prior_slice = df.iloc[-lookback-1:-1]
        if prior_slice.empty:
            prior_slice = df.iloc[:-1]
        session_high = prior_slice['high'].max()
        session_low = prior_slice['low'].min()
        avg_volume = prior_slice['volume'].mean()
        cur_volume = last['volume']

        if avg_volume > 500.0:
            vol_ratio = cur_volume / max(avg_volume, 1.0)
            vol_ok = vol_ratio >= p["min_volume_mult"]
        else:
            candle_rng = max(0.1, last['high'] - last['low'])
            avg_rng = (prior_slice['high'] - prior_slice['low']).mean()
            vol_ratio = candle_rng / max(avg_rng, 0.1)
            vol_ok = vol_ratio >= 1.15

        if spot > session_high and vol_ok and adx >= p["min_adx"]:
            direction = "BUY_CE"
            regime = REGIME_STRONG_BULL
            reason_txt = f"Gamma Breakout BUY CE: Spot {spot:.1f} broke session high {session_high:.1f} with {vol_ratio:.2f}x expansion, ADX {adx:.1f}"
            sig_score = min(96.0, 75.0 + (vol_ratio * 7.0))
        elif spot < session_low and vol_ok and adx >= p["min_adx"]:
            direction = "BUY_PE"
            regime = REGIME_STRONG_BEAR
            reason_txt = f"Gamma Breakdown BUY PE: Spot {spot:.1f} broke session low {session_low:.1f} with {vol_ratio:.2f}x expansion, ADX {adx:.1f}"
            sig_score = min(96.0, 75.0 + (vol_ratio * 7.0))
        else:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=p["target_rr"],
                signal_score=40.0, market_regime=REGIME_NEUTRAL, timeframe_alignment=False,
                confidence=0.0, timestamp=now_str,
                reason=f"Spot {spot:.1f} within session bounds [{session_low:.1f} - {session_high:.1f}] or expansion ratio {vol_ratio:.2f} below threshold",
                thesis_exit_conditions=[]
            )

        contract = options_engine.select_best_option(underlying, direction, spot)
        if not contract:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=p["target_rr"],
                signal_score=50.0, market_regime=regime, timeframe_alignment=True,
                confidence=0.0, timestamp=now_str, reason="Contract selection failed",
                thesis_exit_conditions=[]
            )

        opt_entry = contract.ltp
        delta_abs = max(0.40, abs(contract.delta))
        opt_stop_dist = max(4.0, round(atr * delta_abs * p["atr_stop_multiplier"], 2))
        max_premium_stop = round(opt_entry * p["max_premium_risk_pct"], 2)
        opt_stop_dist = min(opt_stop_dist, max_premium_stop)
        opt_sl = round(max(0.50, opt_entry - opt_stop_dist), 2)
        opt_target = round(opt_entry + (opt_stop_dist * p["target_rr"]), 2)

        total_risk = capital * risk_pct
        risk_per_lot = opt_stop_dist * contract.lot_size
        lots = max(1, int(total_risk // max(risk_per_lot, 1.0)))
        qty = lots * contract.lot_size

        return OptionSignalResult(
            signal_id=sig_id,
            underlying=underlying,
            strategy_code=self.code,
            strategy_name=self.name,
            strategy_version=self.version,
            direction=direction,
            underlying_price=spot,
            option_contract=asdict(contract),
            option_symbol=contract.symbol,
            entry_price=opt_entry,
            stop_loss=opt_sl,
            target=opt_target,
            trailing_type="ATR_TRAILING",
            quantity=qty,
            lots=lots,
            risk_amount=round(lots * risk_per_lot, 2),
            risk_reward=p["target_rr"],
            signal_score=sig_score,
            market_regime=regime,
            timeframe_alignment=True,
            confidence=0.85,
            timestamp=now_str,
            reason=reason_txt,
            thesis_exit_conditions=["VOLUME_EXHAUSTION", "MOMENTUM_REVERSAL", "SESSION_CLOSE_1510"]
        )

# =====================================================================
# STRATEGY 7: INSTITUTIONAL VWAP PULLBACK & REJECT (Index Options Buyer)
# =====================================================================
class StrategyVWAPPullbackRider(BaseOptionStrategy):
    """
    Strategy 7: INSTITUTIONAL VWAP PULLBACK & REJECT (Index Options Buying)
    Trend continuation strategy used by institutional desks.
    Waits for an established trend (15m & 5m alignment) and enters on shallow
    pullbacks into VWAP with candlestick rejection wicks confirming buyers/sellers defense.
    """
    code = "STRAT_VWAP_PULLBACK_RIDER"
    name = "Institutional VWAP Pullback Rider"
    version = "1.0.0"
    description = "Trend-following continuation entering ATM options when price tests VWAP with rejection wick confirmation."
    parameters = {
        "vwap_proximity_pct": 0.0040,  # Within 0.40% of VWAP
        "min_wick_ratio": 0.20,        # Rejection wick >= 20% of total candle
        "adx_min": 16.0,
        "risk_reward": 2.5,
        "atr_stop_multiplier": 1.25,
        "max_premium_risk_pct": 0.25
    }

    def evaluate(
        self,
        underlying: str,
        candles_15m: List[Candle],
        candles_5m: List[Candle],
        candles_1m: List[Candle],
        capital: float = 100000.0,
        risk_pct: float = 0.01,
        params: Optional[Dict[str, Any]] = None
    ) -> OptionSignalResult:
        sig_id = f"sig_vwappb_{uuid.uuid4().hex[:8]}"
        now_str = datetime.utcnow().isoformat()
        p = {**self.parameters, **(params or {})}

        if len(candles_5m) < 20:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=0.0,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=p["risk_reward"],
                signal_score=0.0, market_regime=REGIME_NEUTRAL, timeframe_alignment=False,
                confidence=0.0, timestamp=now_str, reason="Insufficient candles",
                thesis_exit_conditions=[]
            )

        df = pd.DataFrame([c.__dict__ for c in candles_5m])
        df = compute_all_indicators(df)
        last = df.iloc[-1]
        spot = last['close']
        c_open = last['open']
        c_high = last['high']
        c_low = last['low']
        vwap = last.get('vwap', spot)
        ema20 = last.get('ema20', spot)
        ema50 = last.get('ema50', spot)
        atr = last.get('atr14', spot * 0.007)
        adx = last.get('adx', 20.0)

        candle_span = max(c_high - c_low, 1e-4)
        dist_to_vwap = abs(spot - vwap) / max(vwap, 1.0)
        is_near_vwap = dist_to_vwap <= p["vwap_proximity_pct"]

        # Bullish Pullback: Trend is Bullish (EMA20 > EMA50, spot >= vwap*0.998), lower rejection wick
        lower_wick = min(c_open, spot) - c_low
        lower_wick_ratio = lower_wick / candle_span
        is_bull_trend = ema20 > ema50 and adx >= p["adx_min"]

        # Bearish Pullback: Trend is Bearish (EMA20 < EMA50, spot <= vwap*1.002), upper rejection wick
        upper_wick = c_high - max(c_open, spot)
        upper_wick_ratio = upper_wick / candle_span
        is_bear_trend = ema20 < ema50 and adx >= p["adx_min"]

        if is_bull_trend and is_near_vwap and (lower_wick_ratio >= p["min_wick_ratio"] or spot > c_open):
            direction = "BUY_CE"
            regime = REGIME_BULL
            reason_txt = f"VWAP Bullish Pullback Bounce: Spot Rs. {spot:.1f} tested VWAP ({vwap:.1f}) with {lower_wick_ratio*100:.0f}% rejection wick, EMA20 > EMA50"
            sig_score = 80.0
        elif is_bear_trend and is_near_vwap and (upper_wick_ratio >= p["min_wick_ratio"] or spot < c_open):
            direction = "BUY_PE"
            regime = REGIME_BEAR
            reason_txt = f"VWAP Bearish Pullback Fade: Spot Rs. {spot:.1f} tested VWAP ({vwap:.1f}) with {upper_wick_ratio*100:.0f}% rejection wick, EMA20 < EMA50"
            sig_score = 80.0
        else:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=p["risk_reward"],
                signal_score=42.0, market_regime=REGIME_NEUTRAL, timeframe_alignment=False,
                confidence=0.0, timestamp=now_str,
                reason=f"Spot {spot:.1f} not in valid VWAP pullback zone (dist {dist_to_vwap*100:.2f}%) or insufficient wick rejection",
                thesis_exit_conditions=[]
            )

        contract = options_engine.select_best_option(underlying, direction, spot)
        if not contract:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=p["risk_reward"],
                signal_score=50.0, market_regime=regime, timeframe_alignment=True,
                confidence=0.0, timestamp=now_str, reason="Contract selection failed",
                thesis_exit_conditions=[]
            )

        opt_entry = contract.ltp
        delta_abs = max(0.40, abs(contract.delta))
        opt_stop_dist = max(4.0, round(atr * delta_abs * p["atr_stop_multiplier"], 2))
        opt_sl = round(max(0.50, opt_entry - opt_stop_dist), 2)
        opt_target = round(opt_entry + (opt_stop_dist * p["risk_reward"]), 2)

        total_risk = capital * risk_pct
        risk_per_lot = opt_stop_dist * contract.lot_size
        lots = max(1, int(total_risk // max(risk_per_lot, 1.0)))
        qty = lots * contract.lot_size

        return OptionSignalResult(
            signal_id=sig_id,
            underlying=underlying,
            strategy_code=self.code,
            strategy_name=self.name,
            strategy_version=self.version,
            direction=direction,
            underlying_price=spot,
            option_contract=asdict(contract),
            option_symbol=contract.symbol,
            entry_price=opt_entry,
            stop_loss=opt_sl,
            target=opt_target,
            trailing_type="ATR_TRAILING",
            quantity=qty,
            lots=lots,
            risk_amount=round(lots * risk_per_lot, 2),
            risk_reward=p["risk_reward"],
            signal_score=sig_score,
            market_regime=regime,
            timeframe_alignment=True,
            confidence=0.82,
            timestamp=now_str,
            reason=reason_txt,
            thesis_exit_conditions=["VWAP_INVALIDATION", "TREND_REVERSAL", "SESSION_CLOSE_1515"]
        )

# =====================================================================
# STRATEGY 8: CENTRAL PIVOT RANGE (CPR) BREAKOUT (Index Options Buyer)
# =====================================================================
class StrategyCPRBreakout(BaseOptionStrategy):
    """
    Strategy 8: CENTRAL PIVOT RANGE (CPR) BREAKOUT (Index Options Buying)
    Indian benchmark intraday strategy.
    Calculates Pivot, Top Central (TC), and Bottom Central (BC).
    Identifies Narrow CPR regimes which precede explosive directional trending days.
    When price breaks above TC with volume -> BUY CE.
    When price breaks below BC with volume -> BUY PE.
    """
    code = "STRAT_CPR_BREAKOUT"
    name = "Central Pivot Range (CPR) Breakout"
    version = "1.0.0"
    description = "Benchmark Indian index breakout system using Narrow CPR compression and daily pivot level violations."
    parameters = {
        "narrow_cpr_threshold": 0.0030, # CPR width < 0.30% of price
        "volume_mult": 1.20,
        "risk_reward": 3.0,
        "atr_stop_multiplier": 1.30,
        "max_premium_risk_pct": 0.25
    }

    def evaluate(
        self,
        underlying: str,
        candles_15m: List[Candle],
        candles_5m: List[Candle],
        candles_1m: List[Candle],
        capital: float = 100000.0,
        risk_pct: float = 0.01,
        params: Optional[Dict[str, Any]] = None
    ) -> OptionSignalResult:
        sig_id = f"sig_cpr_{uuid.uuid4().hex[:8]}"
        now_str = datetime.utcnow().isoformat()
        p = {**self.parameters, **(params or {})}

        if len(candles_5m) < 20:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=0.0,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=p["risk_reward"],
                signal_score=0.0, market_regime=REGIME_NEUTRAL, timeframe_alignment=False,
                confidence=0.0, timestamp=now_str, reason="Insufficient candles",
                thesis_exit_conditions=[]
            )

        df = pd.DataFrame([c.__dict__ for c in candles_5m])
        df = compute_all_indicators(df)
        last = df.iloc[-1]
        spot = last['close']
        c_open = last['open']
        atr = last.get('atr14', spot * 0.007)

        # Estimate previous session High, Low, Close
        lookback_cpr = min(25, max(5, len(df) - 3))
        prior_bars = df.iloc[-lookback_cpr-1:-1]
        if prior_bars.empty:
            prior_bars = df.iloc[:-1]
        prev_h = prior_bars['high'].max()
        prev_l = prior_bars['low'].min()
        prev_c = prior_bars['close'].iloc[-1]

        pivot = (prev_h + prev_l + prev_c) / 3.0
        bc = (prev_h + prev_l) / 2.0
        tc = (pivot - bc) + pivot

        top_level = max(tc, bc)
        bottom_level = min(tc, bc)
        cpr_width_pct = (top_level - bottom_level) / max(pivot, 1.0)

        recent_vol = last['volume']
        avg_vol = df['volume'].iloc[-20:].mean()
        vol_ok = recent_vol >= (avg_vol * p["volume_mult"])

        if spot > top_level and spot > c_open and vol_ok:
            direction = "BUY_CE"
            regime = REGIME_STRONG_BULL if cpr_width_pct <= p["narrow_cpr_threshold"] else REGIME_BULL
            reason_txt = f"Bullish CPR Breakout on {underlying}: Spot Rs. {spot:.1f} cleared TC Rs. {top_level:.1f} (CPR width: {cpr_width_pct*100:.2f}%) with {recent_vol/max(avg_vol, 1.0):.2f}x volume"
            sig_score = 85.0 if cpr_width_pct <= p["narrow_cpr_threshold"] else 76.0
        elif spot < bottom_level and spot < c_open and vol_ok:
            direction = "BUY_PE"
            regime = REGIME_STRONG_BEAR if cpr_width_pct <= p["narrow_cpr_threshold"] else REGIME_BEAR
            reason_txt = f"Bearish CPR Breakdown on {underlying}: Spot Rs. {spot:.1f} cracked BC Rs. {bottom_level:.1f} (CPR width: {cpr_width_pct*100:.2f}%) with {recent_vol/max(avg_vol, 1.0):.2f}x volume"
            sig_score = 85.0 if cpr_width_pct <= p["narrow_cpr_threshold"] else 76.0
        else:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=p["risk_reward"],
                signal_score=45.0, market_regime=REGIME_NEUTRAL, timeframe_alignment=False,
                confidence=0.0, timestamp=now_str,
                reason=f"Spot {spot:.1f} inside Central Pivot Range [{bottom_level:.1f} - {top_level:.1f}] or volume below {p['volume_mult']}x",
                thesis_exit_conditions=[]
            )

        contract = options_engine.select_best_option(underlying, direction, spot)
        if not contract:
            return OptionSignalResult(
                signal_id=sig_id, underlying=underlying, strategy_code=self.code, strategy_name=self.name,
                strategy_version=self.version, direction="NO_TRADE", underlying_price=spot,
                option_contract=None, option_symbol="", entry_price=0.0, stop_loss=0.0, target=0.0,
                trailing_type="NONE", quantity=0, lots=0, risk_amount=0.0, risk_reward=p["risk_reward"],
                signal_score=50.0, market_regime=regime, timeframe_alignment=True,
                confidence=0.0, timestamp=now_str, reason="Contract selection failed",
                thesis_exit_conditions=[]
            )

        opt_entry = contract.ltp
        delta_abs = max(0.40, abs(contract.delta))
        opt_stop_dist = max(4.0, round(atr * delta_abs * p["atr_stop_multiplier"], 2))
        opt_sl = round(max(0.50, opt_entry - opt_stop_dist), 2)
        opt_target = round(opt_entry + (opt_stop_dist * p["risk_reward"]), 2)

        total_risk = capital * risk_pct
        risk_per_lot = opt_stop_dist * contract.lot_size
        lots = max(1, int(total_risk // max(risk_per_lot, 1.0)))
        qty = lots * contract.lot_size

        return OptionSignalResult(
            signal_id=sig_id,
            underlying=underlying,
            strategy_code=self.code,
            strategy_name=self.name,
            strategy_version=self.version,
            direction=direction,
            underlying_price=spot,
            option_contract=asdict(contract),
            option_symbol=contract.symbol,
            entry_price=opt_entry,
            stop_loss=opt_sl,
            target=opt_target,
            trailing_type="ATR_TRAILING",
            quantity=qty,
            lots=lots,
            risk_amount=round(lots * risk_per_lot, 2),
            risk_reward=p["risk_reward"],
            signal_score=sig_score,
            market_regime=regime,
            timeframe_alignment=True,
            confidence=0.83,
            timestamp=now_str,
            reason=reason_txt,
            thesis_exit_conditions=["CPR_RETEST_FAILURE", "OPPOSITE_PIVOT_BREACH", "SESSION_CLOSE_1515"]
        )

# =====================================================================
# STRATEGY REGISTRY & RESOLVER
# =====================================================================
STRATEGY_REGISTRY: Dict[str, BaseOptionStrategy] = {
    "STRAT_FIXED_RR_13": StrategyFixedRR13(),
    "STRAT_ADAPTIVE_TREND_RIDER": StrategyAdaptiveTrendRider(),
    "STRAT_VOLATILITY_SQUEEZE": StrategyVolatilitySqueeze(),
    "STRAT_ORB_INDEX": StrategyOpeningRangeBreakout(),
    "STRAT_MEAN_REVERSION_EXTREME": StrategyMeanReversionExtreme(),
    "STRAT_EXPIRY_GAMMA_SCALPER": StrategyExpiryGammaScalper(),
    "STRAT_VWAP_PULLBACK_RIDER": StrategyVWAPPullbackRider(),
    "STRAT_CPR_BREAKOUT": StrategyCPRBreakout(),

    # Backwards compatibility aliases
    "STRAT_EMA_VWAP": StrategyFixedRR13(),
    "STRAT_EMA_VWAP_RSI": StrategyFixedRR13(),
    "STRAT_ORB": StrategyOpeningRangeBreakout(),
    "STRAT_VWAP_PULLBACK": StrategyVWAPPullbackRider()
}

def resolve_strategy(strategy_code: str) -> BaseOptionStrategy:
    if not strategy_code:
        return STRATEGY_REGISTRY["STRAT_ADAPTIVE_TREND_RIDER"]
    code = strategy_code.upper().strip()
    if code in STRATEGY_REGISTRY:
        return STRATEGY_REGISTRY[code]
    if "GAMMA" in code or "EXPIRY" in code:
        return STRATEGY_REGISTRY["STRAT_EXPIRY_GAMMA_SCALPER"]
    if "CPR" in code or "PIVOT" in code:
        return STRATEGY_REGISTRY["STRAT_CPR_BREAKOUT"]
    if "PULLBACK" in code:
        return STRATEGY_REGISTRY["STRAT_VWAP_PULLBACK_RIDER"]
    if "ADAPTIVE" in code or "TREND" in code or "RIDER" in code:
        return STRATEGY_REGISTRY["STRAT_ADAPTIVE_TREND_RIDER"]
    if "FIXED" in code or "13" in code or "1:3" in code:
        return STRATEGY_REGISTRY["STRAT_FIXED_RR_13"]
    if "SQUEEZE" in code or "BB" in code:
        return STRATEGY_REGISTRY["STRAT_VOLATILITY_SQUEEZE"]
    if "ORB" in code or "BREAKOUT" in code:
        return STRATEGY_REGISTRY["STRAT_ORB_INDEX"]
    if "REVERSION" in code or "EXTREME" in code:
        return STRATEGY_REGISTRY["STRAT_MEAN_REVERSION_EXTREME"]
    return STRATEGY_REGISTRY["STRAT_ADAPTIVE_TREND_RIDER"]

def get_all_strategies_catalog() -> List[Dict[str, Any]]:
    """Returns metadata catalog of all 8 available Index Options Buying strategies."""
    unique_strats = [
        StrategyFixedRR13(),
        StrategyAdaptiveTrendRider(),
        StrategyVolatilitySqueeze(),
        StrategyOpeningRangeBreakout(),
        StrategyMeanReversionExtreme(),
        StrategyExpiryGammaScalper(),
        StrategyVWAPPullbackRider(),
        StrategyCPRBreakout()
    ]
    catalog = []
    for s in unique_strats:
        catalog.append({
            "code": s.code,
            "name": s.name,
            "version": s.version,
            "description": s.description,
            "parameters": s.parameters,
            "allowed_instruments": ["NIFTY", "BANKNIFTY"],
            "trading_mode": "OPTIONS_BUYING_ONLY",
            "is_active": True
        })
    return catalog

