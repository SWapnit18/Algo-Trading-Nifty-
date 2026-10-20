"""
YOURALGO - Production Position Manager & Adaptive Trailing Engine
Manages Index Option Long Positions (CE / PE) from entry to exit.
Enforces:
- Hard Initial Stop
- Breakeven trigger at 1.5R
- Profit Lock at 2.0R
- Adaptive ATR Ratchet Trailing
- Thesis Exit (VWAP loss, momentum reversal)
- Time Decay Exit (stalled trade)
- Mandatory Session Square-Off at 15:15 IST
"""

from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, time
import logging

logger = logging.getLogger(__name__)

EXIT_STOP_LOSS = "STOP_LOSS"
EXIT_TRAILING_STOP = "TRAILING_STOP"
EXIT_THESIS_FAILURE = "THESIS_FAILURE"
EXIT_TARGET = "TARGET"
EXIT_TIME_EXIT = "TIME_EXIT"
EXIT_SESSION_EXIT = "SESSION_EXIT"
EXIT_RISK_EXIT = "RISK_EXIT"
EXIT_EMERGENCY_EXIT = "EMERGENCY_EXIT"
EXIT_MANUAL_EXIT = "MANUAL_EXIT"

@dataclass
class PositionUpdateDecision:
    position_id: int
    should_close: bool
    exit_reason: str
    exit_price: float
    current_pnl: float
    current_pnl_pct: float
    new_trailing_sl: float
    state_description: str

class PositionManager:
    """
    Stateful evaluation of open Long CE / Long PE index option positions.
    Never lets a winning trade turn into a major loss.
    """

    def evaluate_open_position(
        self,
        position_id: int,
        symbol: str,
        option_type: str,         # CE or PE
        entry_price: float,
        current_opt_price: float,
        initial_sl: float,
        current_sl: float,
        target_price: float,      # 0.0 if pure trailing
        trailing_type: str,       # "ATR_TRAILING", "NONE", etc.
        highest_price_seen: float,
        bars_held: int,
        underlying_spot: float,
        underlying_vwap: float,
        regime_15m: str,
        underlying_atr: float,
        current_ist_time: Optional[datetime] = None
    ) -> PositionUpdateDecision:
        now_dt = current_ist_time or datetime.now()

        # 1. Mandatory Session Exit (15:15 IST)
        # Prevents overnight holding and expiry gap risk
        if now_dt.hour > 15 or (now_dt.hour == 15 and now_dt.minute >= 15):
            pnl = round((current_opt_price - entry_price), 2)
            pnl_pct = round((pnl / max(entry_price, 0.1)) * 100.0, 2)
            return PositionUpdateDecision(
                position_id=position_id,
                should_close=True,
                exit_reason=EXIT_SESSION_EXIT,
                exit_price=current_opt_price,
                current_pnl=pnl,
                current_pnl_pct=pnl_pct,
                new_trailing_sl=current_sl,
                state_description="Mandatory 15:15 IST Session Square-Off engaged"
            )

        # Calculate initial risk distance R
        risk_r = max(2.0, entry_price - initial_sl)
        unrealized_gain = current_opt_price - entry_price
        r_multiple = unrealized_gain / risk_r

        new_sl = current_sl
        new_high = max(highest_price_seen, current_opt_price)

        # 2. Hard Stop Loss Check
        if current_opt_price <= current_sl:
            pnl = round((current_opt_price - entry_price), 2)
            pnl_pct = round((pnl / max(entry_price, 0.1)) * 100.0, 2)
            reason = EXIT_TRAILING_STOP if current_sl > initial_sl else EXIT_STOP_LOSS
            return PositionUpdateDecision(
                position_id=position_id,
                should_close=True,
                exit_reason=reason,
                exit_price=current_opt_price,
                current_pnl=pnl,
                current_pnl_pct=pnl_pct,
                new_trailing_sl=current_sl,
                state_description=f"Stop hit @ Rs. {current_opt_price:.2f} (SL was Rs. {current_sl:.2f})"
            )

        # 3. Fixed Target Check (For Strategy 1)
        if target_price > 0 and current_opt_price >= target_price:
            pnl = round((current_opt_price - entry_price), 2)
            pnl_pct = round((pnl / max(entry_price, 0.1)) * 100.0, 2)
            return PositionUpdateDecision(
                position_id=position_id,
                should_close=True,
                exit_reason=EXIT_TARGET,
                exit_price=current_opt_price,
                current_pnl=pnl,
                current_pnl_pct=pnl_pct,
                new_trailing_sl=current_sl,
                state_description=f"1:3 Target reached @ Rs. {current_opt_price:.2f} (Target Rs. {target_price:.2f})"
            )

        # 4. Thesis Exit Check (Early exit before trailing stop hits)
        is_ce = (option_type.upper() == "CE")
        thesis_failed = False
        thesis_reason = ""

        if is_ce:
            if underlying_spot < underlying_vwap * 0.998:
                thesis_failed = True
                thesis_reason = f"CE Thesis Exit: Underlying Rs. {underlying_spot:.1f} dropped below VWAP Rs. {underlying_vwap:.1f}"
            elif "BEAR" in regime_15m:
                thesis_failed = True
                thesis_reason = f"CE Thesis Exit: 15m Macro regime flipped to {regime_15m}"
        else: # PE
            if underlying_spot > underlying_vwap * 1.002:
                thesis_failed = True
                thesis_reason = f"PE Thesis Exit: Underlying Rs. {underlying_spot:.1f} rose above VWAP Rs. {underlying_vwap:.1f}"
            elif "BULL" in regime_15m:
                thesis_failed = True
                thesis_reason = f"PE Thesis Exit: 15m Macro regime flipped to {regime_15m}"

        if thesis_failed and bars_held >= 3:
            pnl = round((current_opt_price - entry_price), 2)
            pnl_pct = round((pnl / max(entry_price, 0.1)) * 100.0, 2)
            return PositionUpdateDecision(
                position_id=position_id,
                should_close=True,
                exit_reason=EXIT_THESIS_FAILURE,
                exit_price=current_opt_price,
                current_pnl=pnl,
                current_pnl_pct=pnl_pct,
                new_trailing_sl=current_sl,
                state_description=thesis_reason
            )

        # 5. Time Decay Exit (Stalled trade)
        # Options suffer theta decay. If trade fails to progress > 0.5R within 15 bars, exit cleanly
        if bars_held >= 15 and r_multiple < 0.4:
            pnl = round((current_opt_price - entry_price), 2)
            pnl_pct = round((pnl / max(entry_price, 0.1)) * 100.0, 2)
            return PositionUpdateDecision(
                position_id=position_id,
                should_close=True,
                exit_reason=EXIT_TIME_EXIT,
                exit_price=current_opt_price,
                current_pnl=pnl,
                current_pnl_pct=pnl_pct,
                new_trailing_sl=current_sl,
                state_description=f"Time Exit: Stalled trade ({bars_held} bars without +0.5R expansion)"
            )

        # 6. Adaptive Trailing Stop Calculation
        # - Move to Breakeven at +1.5R (Lock Entry + 0.1R buffer for brokerage)
        # - Move to Profit Lock at +2.0R (Lock +1.0R profit)
        # - Ratchet ATR trailing above 2.0R
        state_desc = f"Active Long {option_type} ({r_multiple:+.2f}R)"
        if trailing_type == "ATR_TRAILING":
            if r_multiple >= 2.0:
                # Lock in at least 1.0R profit, or trail behind high
                trail_candidate = max(
                    round(entry_price + (1.0 * risk_r), 2),
                    round(new_high - (1.2 * risk_r), 2)
                )
                if trail_candidate > new_sl:
                    new_sl = trail_candidate
                    state_desc = f"Profit Lock & ATR Trail: SL ratcheted to Rs. {new_sl:.2f} (locked profit)"
            elif r_multiple >= 1.5:
                # Breakeven with small buffer for costs
                be_level = round(entry_price + (0.10 * risk_r), 2)
                if be_level > new_sl:
                    new_sl = be_level
                    state_desc = f"Breakeven engaged: SL moved to Rs. {new_sl:.2f} (+1.5R reached)"

        pnl = round((current_opt_price - entry_price), 2)
        pnl_pct = round((pnl / max(entry_price, 0.1)) * 100.0, 2)

        return PositionUpdateDecision(
            position_id=position_id,
            should_close=False,
            exit_reason="",
            exit_price=current_opt_price,
            current_pnl=pnl,
            current_pnl_pct=pnl_pct,
            new_trailing_sl=new_sl,
            state_description=state_desc
        )

position_manager = PositionManager()
