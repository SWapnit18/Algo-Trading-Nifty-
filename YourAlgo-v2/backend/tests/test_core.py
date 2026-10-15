import pytest
from app.risk import validate_trade, size_position
from app.strategies import STRATEGY_REGISTRY
from app.market_data import Candle

def test_position_sizing():
    qty = size_position(10000, 100, 95, 0.01)
    assert qty == 20

def test_risk_limits_daily_loss():
    decision = validate_trade(
        capital=10000,
        daily_loss=250, # Exceeds 200 limit
        open_positions=0,
        trades_today=0,
        entry=100,
        stop=95,
        target=115
    )
    assert decision.allowed is False
    assert "DAILY_LOSS_LIMIT" in decision.reason

def test_risk_limits_max_positions():
    decision = validate_trade(
        capital=10000,
        daily_loss=0,
        open_positions=2, # Max 2 open positions
        trades_today=0,
        entry=100,
        stop=95,
        target=115
    )
    assert decision.allowed is False
    assert "MAX_OPEN_POSITIONS" in decision.reason

def test_risk_limits_max_trades_per_day():
    decision = validate_trade(
        capital=10000,
        daily_loss=0,
        open_positions=0,
        trades_today=3, # Max 3 entries/day
        entry=100,
        stop=95,
        target=115
    )
    assert decision.allowed is False
    assert "MAX_TRADES_EXCEEDED" in decision.reason

def test_risk_limits_invalid_rr():
    decision = validate_trade(
        capital=10000,
        daily_loss=0,
        open_positions=0,
        trades_today=0,
        entry=100,
        stop=90, # Risk = 10
        target=110 # Reward = 10 (RR 1:1, below 1:2 minimum)
    )
    assert decision.allowed is False
    assert "INVALID_RISK_REWARD" in decision.reason

def test_strategy_orb_evaluation():
    strat = STRATEGY_REGISTRY["STRAT_ORB"]
    candles = [Candle("2026-10-09 09:15:00", 100, 105, 95, 100, 50000) for _ in range(25)]
    res = strat.evaluate("RELIANCE", candles, capital=10000, risk_pct=0.01)
    assert res.direction in ["BUY", "NO_TRADE"]
    assert res.risk_reward == 3.0
