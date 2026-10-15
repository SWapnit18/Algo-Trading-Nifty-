from dataclasses import dataclass
from .config import settings

@dataclass
class RiskDecision:
    allowed: bool
    reason: str
    risk_amount: float
    quantity: int

def size_position(capital: float, entry: float, stop: float, risk_pct: float = 0.01) -> int:
    """
    AC-06 / AC-16 Dynamic position sizing:
    risk_amount = account_equity * risk_percentage
    risk_per_share = abs(entry - stop)
    quantity = floor(risk_amount / risk_per_share)
    """
    if entry <= 0 or stop <= 0 or entry == stop or capital <= 0:
        return 0
    risk_amount = capital * risk_pct
    risk_per_share = abs(entry - stop)
    if risk_per_share <= 0:
        return 0
    return max(0, int(risk_amount // risk_per_share))

def validate_trade(
    capital: float,
    daily_loss: float,
    open_positions: int,
    trades_today: int,
    entry: float,
    stop: float,
    target: float = 0.0,
    available_cash: float = 0.0,
    kill_switch_active: bool = False,
    market_feed_status: str = "LIVE",
    risk_pct: float = 0.01,
    daily_loss_limit: float = 200.0,
    max_open_positions: int = 2,
    max_trades_per_day: int = 3
) -> RiskDecision:
    risk_amount = round(capital * risk_pct, 2)

    # AC-30 Kill switch
    if kill_switch_active:
        return RiskDecision(False, "KILL_SWITCH_ACTIVE: All new orders blocked", risk_amount, 0)

    # AC-08 / AC-09 Stale or unconfigured market data protection
    if market_feed_status == "STALE":
        return RiskDecision(False, "STALE_DATA_PROTECTION: Market data is stale, new entries blocked", risk_amount, 0)
    if market_feed_status in ["NOT CONFIGURED", "DISCONNECTED"]:
        return RiskDecision(False, "MARKET_DATA_UNAVAILABLE: Feed not connected or configured", risk_amount, 0)

    # AC-17 Daily loss limit
    if daily_loss >= daily_loss_limit:
        return RiskDecision(False, f"DAILY_LOSS_LIMIT: Limit (₹{daily_loss_limit:.2f}) reached (Current loss: ₹{daily_loss:.2f})", risk_amount, 0)

    # AC-18 Maximum open positions
    if open_positions >= max_open_positions:
        return RiskDecision(False, f"MAX_OPEN_POSITIONS: Maximum open positions ({max_open_positions}) reached", risk_amount, 0)

    # AC-19 Maximum trades per day
    if trades_today >= max_trades_per_day:
        return RiskDecision(False, f"MAX_TRADES_EXCEEDED: Maximum daily entries ({max_trades_per_day}) reached", risk_amount, 0)

    # Price levels
    if entry <= 0 or stop <= 0 or entry == stop:
        return RiskDecision(False, "INVALID_PRICE_LEVELS: Invalid entry or stop-loss level", risk_amount, 0)

    stop_distance = abs(entry - stop)
    if target > 0:
        reward_distance = abs(target - entry)
        rr = reward_distance / stop_distance
        if rr < 1.95:  # AC specifies 1:3 default with at least 1:2
            return RiskDecision(False, f"INVALID_RISK_REWARD: RR ratio ({rr:.2f}) is below minimum acceptable 1:2", risk_amount, 0)

    qty = size_position(capital, entry, stop, risk_pct)
    if qty <= 0:
        return RiskDecision(False, "ZERO_QUANTITY: Position sizing resulted in 0 shares", risk_amount, 0)

    order_cost = qty * entry
    if order_cost > available_cash:
        possible_qty = int(available_cash // entry)
        if possible_qty <= 0:
            return RiskDecision(False, f"INSUFFICIENT_CASH: Required ₹{order_cost:.2f}, available cash is ₹{available_cash:.2f}", risk_amount, 0)
        qty = possible_qty

    return RiskDecision(True, "RISK_APPROVED: All checks passed successfully", risk_amount, qty)
