import pytest
import asyncio
from app.brokers.manager import broker_manager
from app.brokers.upstox import UpstoxAdapter
from app.security_vault import encrypt_secret, decrypt_secret, mask_account_id
from app.automation_engine import automation_engine
from app.indicators import calculate_black_scholes_greeks, generate_option_chain_snapshot

def test_security_vault_encryption():
    raw_token = "upstox_live_jwt_secret_token_12345"
    encrypted = encrypt_secret(raw_token)
    assert encrypted != raw_token
    assert len(encrypted) > 20
    decrypted = decrypt_secret(encrypted)
    assert decrypted == raw_token

def test_mask_account_id():
    assert mask_account_id("DEMO_CLIENT_ID_1234") == "XXXX1234"
    assert mask_account_id("44") == "XXXX44"
    assert mask_account_id("") == "XXXX1234"

def test_broker_manager_adapters():
    # In YourAlgo v2, Upstox is the ONLY broker supported
    upstox = broker_manager.get_adapter("UPSTOX", access_token="tok", api_key="k")
    assert upstox.name == "UPSTOX"

    paper = broker_manager.get_adapter("PAPER")
    assert paper.name == "PAPER"

    # Any unconfigured or removed broker falls safely back to PaperAdapter
    other = broker_manager.get_adapter("OTHER")
    assert other.name == "PAPER"

@pytest.mark.anyio
async def test_paper_adapter_order_flow():
    paper = broker_manager.get_adapter("PAPER")
    res = await paper.place_order(symbol="RELIANCE", side="BUY", quantity=10, price=2850.0)
    assert res["status"] == "FILLED"
    assert res["symbol"] == "RELIANCE"

    positions = await paper.get_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "RELIANCE"
    assert positions[0]["quantity"] == 10

    # Test exit
    exit_res = await paper.close_position("RELIANCE", quantity=10)
    assert exit_res["status"] == "FILLED"
    positions_after = await paper.get_positions()
    assert len(positions_after) == 0

def test_automation_engine_controls():
    assert not automation_engine.is_running
    automation_engine.start()
    assert automation_engine.is_running
    automation_engine.stop()
    assert not automation_engine.is_running

@pytest.mark.anyio
async def test_upstox_adapter_flow():
    upstox = UpstoxAdapter(access_token="mock_upstox_token", api_key="DEMO_CLIENT_ID_1234")
    assert upstox.name == "UPSTOX"

    # Test login URL generation
    login_url = upstox.get_login_url()
    assert "https://api.upstox.com/v2/login/authorization/dialog" in login_url
    assert "DEMO_CLIENT_ID_1234" in login_url

    # Test mock token exchange
    token_res = await upstox.exchange_auth_code("DEMO_CODE_123")
    assert token_res["status"] == "SUCCESS"
    assert "access_token" in token_res["token_data"]

    # Test mock profile
    profile = await upstox.get_profile()
    assert "client_id" in profile

    # Test funds and margins
    balance = await upstox.get_balance()
    assert "available_cash" in balance
    assert balance["available_cash"] >= 0

    # Test quote
    quote = await upstox.get_quote("RELIANCE")
    assert quote["symbol"] == "RELIANCE"
    assert quote["source"] == "UPSTOX_LIVE"

    # Test positions
    positions = await upstox.get_positions()
    assert isinstance(positions, list)

    # Test place order
    order_res = await upstox.place_order(symbol="RELIANCE", side="BUY", quantity=5, order_type="MARKET", price=1285.5)
    assert order_res["status"] in ["SUBMITTED", "FILLED"]
    assert order_res["broker"] == "UPSTOX"

    # Test exit all positions
    exit_res = await upstox.exit_all_positions()
    assert exit_res["status"] == "SUCCESS"

def test_black_scholes_greeks_and_option_chain():
    # Test Greeks
    greeks = calculate_black_scholes_greeks(
        spot=25050.0,
        strike=25050.0,
        time_to_expiry_years=7 / 365.0,
        volatility=0.135,
        risk_free_rate=0.065,
        option_type="CE"
    )
    assert greeks["status"] == "SUCCESS"
    assert "delta" in greeks
    assert "gamma" in greeks
    assert "theta" in greeks
    assert "vega" in greeks
    assert "rho" in greeks
    assert "iv" in greeks
    assert 0.0 <= greeks["delta"] <= 1.0
    assert greeks["gamma"] > 0
    assert greeks["theta"] < 0
    assert greeks["iv"] > 0

    # Test Option Chain
    chain = generate_option_chain_snapshot(underlying="NIFTY")
    assert chain["underlying"] == "NIFTY"
    assert len(chain["strikes"]) > 0
    first_strike = chain["strikes"][0]
    assert "strike_price" in first_strike
    assert "call" in first_strike
    assert "put" in first_strike
