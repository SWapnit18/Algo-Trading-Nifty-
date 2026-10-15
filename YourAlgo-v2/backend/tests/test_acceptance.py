import pytest
from app.risk import validate_trade, size_position
from app.strategies import STRATEGY_REGISTRY
from app.market_data import Candle, market_service

def test_dynamic_capital_position_sizing():
    # AC-06 Dynamic Capital: with capital = 50,000 and 1% risk = 500 risk
    # Entry 100, Stop 95 -> risk/share = 5 -> qty = 100
    qty = size_position(50000, 100, 95, 0.01)
    assert qty == 100

    # With capital = 100,000 -> qty = 200
    qty_high = size_position(100000, 100, 95, 0.01)
    assert qty_high == 200

def test_stale_market_data_protection():
    # AC-09 Stale data protection: new orders blocked
    decision = validate_trade(
        capital=50000,
        daily_loss=0,
        open_positions=0,
        trades_today=0,
        entry=100,
        stop=95,
        target=115,
        available_cash=50000,
        market_feed_status="STALE"
    )
    assert decision.allowed is False
    assert "STALE_DATA_PROTECTION" in decision.reason

def test_unconfigured_market_data_protection():
    # AC-08 No fake market data: feed must be connected/configured
    decision = validate_trade(
        capital=50000,
        daily_loss=0,
        open_positions=0,
        trades_today=0,
        entry=100,
        stop=95,
        target=115,
        available_cash=50000,
        market_feed_status="NOT CONFIGURED"
    )
    assert decision.allowed is False
    assert "MARKET_DATA_UNAVAILABLE" in decision.reason

def test_daily_loss_limit_rejection():
    # AC-17 Daily loss limit rejection
    decision = validate_trade(
        capital=50000,
        daily_loss=250, # Exceeds 200 limit
        open_positions=0,
        trades_today=0,
        entry=100,
        stop=95,
        target=115,
        available_cash=50000,
        market_feed_status="LIVE"
    )
    assert decision.allowed is False
    assert "DAILY_LOSS_LIMIT" in decision.reason

def test_max_open_positions_rejection():
    # AC-18 Max open positions rejection
    decision = validate_trade(
        capital=50000,
        daily_loss=0,
        open_positions=2, # Limit is 2
        trades_today=0,
        entry=100,
        stop=95,
        target=115,
        available_cash=50000,
        market_feed_status="LIVE"
    )
    assert decision.allowed is False
    assert "MAX_OPEN_POSITIONS" in decision.reason

def test_max_daily_trades_rejection():
    # AC-19 Max daily trades rejection
    decision = validate_trade(
        capital=50000,
        daily_loss=0,
        open_positions=0,
        trades_today=3, # Limit is 3 entries
        entry=100,
        stop=95,
        target=115,
        available_cash=50000,
        market_feed_status="LIVE"
    )
    assert decision.allowed is False
    assert "MAX_TRADES_EXCEEDED" in decision.reason

def test_kill_switch_active_rejection():
    # AC-30 Kill switch active rejection
    decision = validate_trade(
        capital=50000,
        daily_loss=0,
        open_positions=0,
        trades_today=0,
        entry=100,
        stop=95,
        target=115,
        available_cash=50000,
        kill_switch_active=True,
        market_feed_status="LIVE"
    )
    assert decision.allowed is False
    assert "KILL_SWITCH_ACTIVE" in decision.reason

def test_all_strategies_produce_actionable_signals():
    # AC-14 / AC-15: Strategies generate valid reproducible signals
    candles = [Candle("2026-10-09 09:15:00", 100, 105, 95, 100, 50000) for _ in range(60)]
    for code, strat in STRATEGY_REGISTRY.items():
        res = strat.evaluate("RELIANCE", candles, capital=50000, risk_pct=0.01)
        assert res.direction in ["BUY", "NO_TRADE"]
        assert res.risk_reward == 3.0
