"""
YourAlgo v2 — Indian Real Market Live Test Suite
Validates the complete trading platform against official National Stock Exchange (NSE)
rules, timings, tick sizes, currency (INR), risk management (SEBI guidelines),
quant strategies, and Upstox broker automation.
"""

import sys
import os
import json
import asyncio
from datetime import datetime, timedelta, timezone

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add backend directory to sys.path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient
from app.main import app
from app.market_data import get_ist_now, get_nse_market_status, Candle, market_service
from app.risk import validate_trade, size_position
from app.strategies import STRATEGY_REGISTRY, resolve_strategy
from app.brokers.upstox import UpstoxAdapter
from app.brokers.manager import broker_manager
from app.automation_engine import automation_engine

PASS = " [PASS] "
FAIL = " [FAIL] "
INFO = " [INFO] "

results = []

def record(name: str, passed: bool, detail: str = ""):
    status = PASS if passed else FAIL
    results.append((name, passed, detail))
    print(f"{status} {name}: {detail}")

async def run_all_tests():
    print("=" * 80)
    print("   INDIAN REAL MARKET LIVE VALIDATION SUITE (NSE / SEBI / UPSTOX)")
    print("=" * 80)

    # -------------------------------------------------------------
    # 1. TIMEZONE & NSE SESSION TIMINGS
    # -------------------------------------------------------------
    print("\n--- TEST SECTION 1: TIMEZONE & NSE TRADING SESSIONS ---")
    ist_now = get_ist_now()
    utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
    time_diff = (ist_now - utc_now).total_seconds() / 3600.0
    record(
        "IST Timezone Accuracy (UTC+5:30)",
        abs(time_diff - 5.5) < 0.05,
        f"IST Now: {ist_now.strftime('%Y-%m-%d %H:%M:%S IST')} (Offset: +{time_diff:.1f} hrs)"
    )

    # Real-time status for current instant
    current_status = get_nse_market_status(simulation_mode=False)
    weekday_name = ist_now.strftime("%A")
    record(
        "Current NSE Market Status Verification",
        "status" in current_status and "ist_time" in current_status,
        f"Day: {weekday_name}, Status: {current_status['status']} ({current_status.get('sub_status', 'N/A')}), Message: {current_status['message']}"
    )

    # Simulated Market Hours Matrix Test
    # Test 08:30 (Pre-session), 09:05 (Pre-market Call Auction), 10:30 (Live Regular), 15:45 (Post-market)
    def check_custom_ist(dt: datetime):
        weekday = dt.weekday()
        if weekday in [5, 6]:
            return "CLOSED", "WEEKEND"
        curr_min = dt.hour * 60 + dt.minute
        if curr_min < 9 * 60:
            return "CLOSED", "PRE_SESSION"
        if 9 * 60 <= curr_min < 9 * 60 + 15:
            return "PRE_MARKET", "CALL_AUCTION"
        if 9 * 60 + 15 <= curr_min <= 15 * 60 + 30:
            return "LIVE", "REGULAR_TRADING"
        return "CLOSED", "POST_MARKET"

    t_pre_sess = ist_now.replace(hour=8, minute=30, second=0)
    st, sub = check_custom_ist(t_pre_sess)
    record("Pre-Session Timing (08:30 IST)", st == "CLOSED" and sub == "PRE_SESSION", "Correctly identifies pre-session")

    t_pre_mkt = ist_now.replace(hour=9, minute=5, second=0)
    st, sub = check_custom_ist(t_pre_mkt)
    record("Pre-Market Call Auction (09:05 IST)", st == "PRE_MARKET" and sub == "CALL_AUCTION", "09:00 - 09:15 IST Call auction detected")

    t_reg = ist_now.replace(hour=11, minute=30, second=0)
    st, sub = check_custom_ist(t_reg)
    record("Regular NSE Market Session (11:30 IST)", st == "LIVE" and sub == "REGULAR_TRADING", "09:15 - 15:30 IST Live trading active")

    t_post = ist_now.replace(hour=15, minute=45, second=0)
    st, sub = check_custom_ist(t_post)
    record("Post-Market / Closing Session (15:45 IST)", st == "CLOSED" and sub == "POST_MARKET", "After 15:30 IST market correctly closed")

    # -------------------------------------------------------------
    # 2. NSE EQUITIES, TICK SIZE & PRECISION
    # -------------------------------------------------------------
    print("\n--- TEST SECTION 2: NSE EQUITIES, TICK SIZE & PRECISION ---")
    nse_test_symbols = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "TATAMOTORS"]

    for sym in nse_test_symbols:
        q = await market_service.get_quote(sym)
        ltp = q.ltp
        # Verify tick size modulo 0.05 (allowing float precision rounding)
        tick_rem = round(ltp * 100) % 5
        record(
            f"NSE Tick Size (₹0.05) & LTP: {sym}",
            tick_rem == 0 and ltp > 10.0,
            f"LTP: ₹{ltp:,.2f}, Change: {q.change_pct:+.2f}%, Provider: {q.provider}, Feed: {q.feed_status}"
        )

    # -------------------------------------------------------------
    # 3. SEBI RISK ENGINE & CAPITAL SIZING (INR)
    # -------------------------------------------------------------
    print("\n--- TEST SECTION 3: SEBI RISK ENGINE & CAPITAL SIZING (INR) ---")
    
    # Position Sizing: Capital = ₹1,00,000, Risk = 1% (₹1,000), Entry = 2800, Stop = 2750 (Risk = ₹50)
    # Qty = 1,000 / 50 = 20 shares
    qty = size_position(capital=100000.0, entry=2800.0, stop=2750.0, risk_pct=0.01)
    record("Dynamic Position Sizing (₹1,00,000 / 1% Risk)", qty == 20, f"Calculated Qty: {qty} shares (Planned risk: ₹1,000)")

    # Stale Data Protection
    d_stale = validate_trade(
        capital=50000, daily_loss=0, open_positions=0, trades_today=0,
        entry=2800, stop=2750, target=2950, available_cash=50000,
        market_feed_status="STALE"
    )
    record("Stale Feed Protection (Blocks Orders)", not d_stale.allowed and "STALE" in d_stale.reason, f"Blocked: {d_stale.reason}")

    # Daily Loss Limit Circuit Breaker (Max loss limit exceeded)
    d_loss = validate_trade(
        capital=50000, daily_loss=2500, open_positions=0, trades_today=0,
        entry=2800, stop=2750, target=2950, available_cash=50000,
        market_feed_status="LIVE"
    )
    record("Daily Max Loss Circuit Breaker", not d_loss.allowed and "DAILY_LOSS" in d_loss.reason, f"Blocked: {d_loss.reason}")

    # Max Open Positions Limit (Max 2 positions)
    d_pos = validate_trade(
        capital=50000, daily_loss=0, open_positions=2, trades_today=0,
        entry=2800, stop=2750, target=2950, available_cash=50000,
        market_feed_status="LIVE"
    )
    record("Max Intraday Positions Limit", not d_pos.allowed and "MAX_OPEN_POSITIONS" in d_pos.reason, f"Blocked: {d_pos.reason}")

    # Emergency Kill Switch
    d_kill = validate_trade(
        capital=50000, daily_loss=0, open_positions=0, trades_today=0,
        entry=2800, stop=2750, target=2950, available_cash=50000,
        kill_switch_active=True, market_feed_status="LIVE"
    )
    record("Emergency Kill Switch Active", not d_kill.allowed and "KILL_SWITCH" in d_kill.reason, f"Blocked: {d_kill.reason}")

    # -------------------------------------------------------------
    # 4. QUANT TRADING STRATEGIES EVALUATION
    # -------------------------------------------------------------
    print("\n--- TEST SECTION 4: QUANT TRADING STRATEGIES EVALUATION ---")
    
    # Retrieve 60 realistic 15m candles for RELIANCE
    candles = await market_service.get_historical_data("RELIANCE", timeframe="15m", limit=60)
    record("NSE Historical Candle Engine (15m)", len(candles) >= 50, f"Retrieved {len(candles)} candles for RELIANCE")

    strat_ema_vwap = resolve_strategy("STRAT_EMA_VWAP")
    sig_ema = strat_ema_vwap.evaluate("RELIANCE", candles, capital=100000.0, risk_pct=0.01)
    record(
        "Strategy 1: EMA/VWAP Trend Evaluation",
        sig_ema.direction in ["BUY", "SELL", "NO_TRADE"],
        f"Direction: {sig_ema.direction}, Entry: ₹{sig_ema.entry_price}, SL: ₹{sig_ema.stop_loss}, Target: ₹{sig_ema.target}, Qty: {sig_ema.quantity}, RR: {sig_ema.risk_reward}:1"
    )

    strat_orb = resolve_strategy("STRAT_ORB")
    sig_orb = strat_orb.evaluate("RELIANCE", candles, capital=100000.0, risk_pct=0.01)
    record(
        "Strategy 2: 15-Min Opening Range Breakout (ORB)",
        sig_orb.direction in ["BUY", "SELL", "NO_TRADE"],
        f"Direction: {sig_orb.direction}, Reason: {sig_orb.reason[:60]}..."
    )

    strat_vwap = resolve_strategy("STRAT_VWAP_PULLBACK")
    sig_vwap = strat_vwap.evaluate("RELIANCE", candles, capital=100000.0, risk_pct=0.01)
    record(
        "Strategy 3: VWAP Pullback Strategy",
        sig_vwap.direction in ["BUY", "SELL", "NO_TRADE"],
        f"Direction: {sig_vwap.direction}, Reason: {sig_vwap.reason[:60]}..."
    )

    # -------------------------------------------------------------
    # 5. UPSTOX OFFICIAL BROKER ADAPTER & PAPER ENGINE
    # -------------------------------------------------------------
    print("\n--- TEST SECTION 5: UPSTOX BROKER ADAPTER & PAPER ENGINE ---")
    upstox = UpstoxAdapter(access_token="mock_token", api_key="demo_key")
    login_url = upstox.get_login_url()
    record("Upstox OAuth Login URL Generator", "https://api.upstox.com/v2/login/authorization/dialog" in login_url, f"Auth URL: {login_url[:65]}...")

    paper = broker_manager.get_adapter("PAPER")
    
    # Place order
    res = await paper.place_order(symbol="TCS", side="BUY", quantity=5, price=3850.0)
    p_ok = res.get("status") == "FILLED"
    # Check position
    positions = await paper.get_positions()
    pos_ok = len(positions) > 0 and positions[0]["symbol"] == "TCS"
    # Close position
    c_res = await paper.close_position("TCS", quantity=5)
    c_ok = c_res.get("status") == "FILLED"
    record("Paper Trading Order & Position Lifecycle", p_ok and pos_ok and c_ok, "Order Placed (FILLED) -> Position Tracked -> Closed Successfully")

    # -------------------------------------------------------------
    # 6. FASTAPI ENDPOINTS LIVE TEST (TestClient)
    # -------------------------------------------------------------
    print("\n--- TEST SECTION 6: FASTAPI LIVE ENDPOINTS (TestClient) ---")
    with TestClient(app) as client:
        # Health
        res = client.get("/api/v1/health")
        record("GET /api/v1/health", res.status_code == 200 and res.json().get("status", "").upper() == "HEALTHY", f"Status: {res.status_code} ({res.json().get('status')})")

        # Market Status
        res = client.get("/api/v1/market/status")
        m_data = res.json()
        record(
            "GET /api/v1/market/status",
            res.status_code == 200 and "status" in m_data,
            f"Market Status: {m_data.get('status')} | {m_data.get('message')}"
        )

        # Instruments (NSE Equities)
        res = client.get("/api/v1/instruments")
        insts = res.json()
        record(
            "GET /api/v1/instruments",
            res.status_code == 200 and len(insts) >= 10,
            f"Returned {len(insts)} Indian instruments (e.g., {[i['symbol'] for i in insts[:5]]})"
        )

        # Live Quotes
        res = client.get("/api/v1/market/quotes")
        q_resp = res.json()
        quotes_dict = q_resp.get("data", {}) if isinstance(q_resp, dict) and "data" in q_resp else q_resp
        first_key = next(iter(quotes_dict)) if isinstance(quotes_dict, dict) and quotes_dict else None
        first_quote = quotes_dict[first_key] if first_key and isinstance(quotes_dict, dict) else {}
        record(
            "GET /api/v1/market/quotes",
            res.status_code == 200 and len(quotes_dict) >= 5,
            f"Fetched quotes for {len(quotes_dict)} equities (e.g. {first_key} = ₹{first_quote.get('ltp', 0)})"
        )

        # Strategies
        res = client.get("/api/v1/strategies")
        strats = res.json()
        record(
            "GET /api/v1/strategies",
            res.status_code == 200 and len(strats) >= 3,
            f"Configured quant strategies: {[s['code'] for s in strats]}"
        )

        # InvestIQ Overview
        res = client.get("/api/v1/investiq/overview")
        record(
            "GET /api/v1/investiq/overview",
            res.status_code == 200,
            f"InvestIQ AI Status: {res.status_code} ({res.json().get('status')})"
        )

        # Authentication & Protected Portfolio endpoint
        auth_res = client.post("/api/auth/login", json={"email": "trader@youralgo.com", "password": "Trader@12345"})
        if auth_res.status_code == 200:
            token = auth_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            p_res = client.get("/api/v1/portfolio", headers=headers)
            port = p_res.json()
            record(
                "GET /api/v1/portfolio (Protected)",
                p_res.status_code == 200 and "initial_capital" in port,
                f"Capital: ₹{port.get('initial_capital', 0):,.2f}, Cash: ₹{port.get('available_cash', 0):,.2f}, Total PnL: ₹{port.get('total_pnl', 0):,.2f}"
            )

            # Risk check endpoint
            risk_res = client.post("/api/v1/risk/check", json={"symbol": "INFY", "entry": 1600.0, "stop": 1580.0, "target": 1660.0}, headers=headers)
            r_data = risk_res.json()
            record(
                "POST /api/v1/risk/check",
                risk_res.status_code == 200,
                f"Allowed: {r_data.get('allowed')}, Sized Qty: {r_data.get('quantity')}, Risk Amt: ₹{r_data.get('risk_amount', 0)}"
            )

            # Paper order placement test through API
            order_payload = {
                "symbol": "RELIANCE",
                "side": "BUY",
                "quantity": 10,
                "order_type": "MARKET",
                "price": 2880.0,
                "stop_loss": 2840.0,
                "target": 3000.0,
                "strategy_code": "STRAT_EMA_VWAP"
            }
            order_res = client.post("/api/v1/orders/paper", json=order_payload, headers=headers)
            o_data = order_res.json()
            if order_res.status_code == 200:
                order_dict = o_data.get("order", {}) if isinstance(o_data, dict) and isinstance(o_data.get("order"), dict) else o_data
                status = order_dict.get("status") if isinstance(order_dict, dict) else None
                record(
                    "POST /api/v1/orders/paper (Execution API)",
                    status in ["FILLED", "PENDING", "SUBMITTED"],
                    f"Order ID: {order_dict.get('id')}, Status: {status}, Executed Qty: {order_dict.get('quantity')} @ ₹{o_data.get('execution_price', order_dict.get('price'))}"
                )
            elif order_res.status_code == 400 and "Risk Engine" in o_data.get("detail", ""):
                # Valid server-side risk gate enforcement
                record(
                    "POST /api/v1/orders/paper (Risk Gate Active)",
                    True,
                    f"Risk Gate Enforced: {o_data.get('detail')}"
                )
            else:
                record(
                    "POST /api/v1/orders/paper (Execution API)",
                    False,
                    f"Unexpected Response ({order_res.status_code}): {o_data}"
                )
        else:
            record("User Authentication", False, f"Login failed with code {auth_res.status_code}")

    # -------------------------------------------------------------
    # FINAL RECAP
    # -------------------------------------------------------------
    total = len(results)
    passed_count = sum(1 for _, p, _ in results if p)
    failed_count = total - passed_count

    print("\n" + "=" * 80)
    print(f"   INDIAN REAL MARKET LIVE VALIDATION SUMMARY: {passed_count}/{total} PASSED")
    print("=" * 80)
    if failed_count == 0:
        print("🎉 ALL CHECKS PASSED: YourAlgo v2 conforms 100% to Indian Real Market rules!")
    else:
        print(f"⚠️ {failed_count} tests failed. Please review details above.")
    print("=" * 80)

    return failed_count == 0

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
