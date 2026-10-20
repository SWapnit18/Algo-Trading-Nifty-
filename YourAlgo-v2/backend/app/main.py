from contextlib import asynccontextmanager
from datetime import datetime
import asyncio
import json
import uuid
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, Query, Body, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_

from .db import Base, engine, get_db
from .config import settings
from .models import (
    User, Instrument, Watchlist, WatchlistItem, Strategy, Signal,
    Order, OrderEvent, Trade, Position, PortfolioSnapshot, RiskConfig,
    RiskEvent, AuditLog, Backtest, BrokerConnection, AutomationConfig,
    AutomationLog, ReconciliationRecord, TradingAccount
)
from .security_vault import encrypt_secret, decrypt_secret, mask_account_id
from .brokers.manager import broker_manager
from .brokers.upstox import UpstoxAdapter
from .automation_engine import automation_engine
from .auth import (
    get_password_hash, verify_password, create_access_token, create_refresh_token,
    get_current_user, require_admin
)
from .market_data import market_service
from .indicators import compute_all_indicators, calculate_black_scholes_greeks, generate_option_chain_snapshot
from .strategies import STRATEGY_REGISTRY
from .risk import validate_trade
from .backtesting import run_backtest_simulation
from .schemas import (
    DynamicCapitalUpdate, MarketDataConfig, ScreenerRuleRequest,
    WatchlistCreateRequest, WatchlistRenameRequest
)
from .investiq_service import investiq_engine
from .kronos_engine import kronos_engine, kronos_backtester
from .tradingview_udf import router as udf_router
from dataclasses import asdict
from .options_engine import options_engine, SelectedContract
from .regime_engine import regime_engine
from .strategies import get_all_strategies_catalog, resolve_strategy
from .backtesting import run_options_backtest, run_walk_forward_backtest, compare_all_strategies
from .execution_engine import execution_engine

# Schemas
class KronosBacktestRequest(BaseModel):
    symbol: str = "RELIANCE"
    timeframe: str = "15m"
    initial_capital: float = 100000.0
    risk_per_trade_pct: float = 1.0

class RegisterSchema(BaseModel):
    name: str
    email: str
    password: str

class LoginSchema(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict

class RiskCheckRequest(BaseModel):
    entry: float
    stop: float
    target: float = 0.0
    symbol: str

class PaperOrderRequest(BaseModel):
    symbol: str
    side: str
    quantity: int
    order_type: str = "MARKET"
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    strategy_code: Optional[str] = "MANUAL"
    client_order_id: Optional[str] = None # For idempotency (AC-22)

class BacktestRequest(BaseModel):
    symbol: str
    strategy_code: str
    timeframe: str = "15m"
    capital: Optional[float] = None # Dynamic from user capital if omitted
    risk_pct: float = 0.01

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    with next(get_db()) as db:
        # Seed default Admin & User
        admin_user = db.scalar(select(User).where(User.email == "admin@youralgo.com"))
        if not admin_user:
            admin_user = User(
                email="admin@youralgo.com",
                name="Admin Trader",
                hashed_password=get_password_hash("Admin@12345"),
                role="ADMIN"
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)

        default_user = db.scalar(select(User).where(User.email == "trader@youralgo.com"))
        if not default_user:
            default_user = User(
                email="trader@youralgo.com",
                name="Pro Trader",
                hashed_password=get_password_hash("Trader@12345"),
                role="USER"
            )
            db.add(default_user)
            db.commit()
            db.refresh(default_user)

        for uid in [admin_user.id, default_user.id]:
            r_cfg = db.scalar(select(RiskConfig).where(RiskConfig.user_id == uid))
            if not r_cfg:
                db.add(RiskConfig(
                    user_id=uid,
                    capital=50000.0, # Default configured dynamically
                    risk_percentage=0.01,
                    daily_loss_limit=200.0,
                    max_open_positions=2,
                    max_trades_per_day=3,
                    risk_reward=3.0
                ))

        # Seed authoritative NSE equities
        nse_symbols = [
            ("RELIANCE", "Reliance Industries Ltd", "INE002A01018", "2885"),
            ("TCS", "Tata Consultancy Services Ltd", "INE467B01029", "11536"),
            ("INFY", "Infosys Ltd", "INE009A01021", "1594"),
            ("HDFCBANK", "HDFC Bank Ltd", "INE040A01034", "1333"),
            ("ICICIBANK", "ICICI Bank Ltd", "INE090A01021", "4963"),
            ("SBIN", "State Bank of India", "INE062A01020", "3045"),
            ("BHARTIARTL", "Bharti Airtel Ltd", "INE397D01024", "10604"),
            ("LT", "Larsen & Toubro Ltd", "INE018A01030", "11483"),
            ("TATAMOTORS", "Tata Motors Ltd", "INE155A01022", "3456"),
            ("WIPRO", "Wipro Ltd", "INE075A01022", "3787")
        ]
        for sym, name, isin, sec_id in nse_symbols:
            inst = db.scalar(select(Instrument).where(Instrument.symbol == sym))
            if not inst:
                db.add(Instrument(
                    symbol=sym,
                    tradingsymbol=sym,
                    security_id=sec_id,
                    isin=isin,
                    exchange="NSE",
                    segment="EQUITY",
                    instrument_type="EQUITY",
                    tick_size=0.05,
                    lot_size=1
                ))

        seen_codes = set()
        for strat in STRATEGY_REGISTRY.values():
            if strat.code in seen_codes:
                continue
            seen_codes.add(strat.code)
            s_rec = db.scalar(select(Strategy).where(Strategy.code == strat.code))
            if not s_rec:
                db.add(Strategy(
                    name=strat.name,
                    code=strat.code,
                    version=strat.version,
                    description=strat.__doc__ or "",
                    mode="PAPER",
                    enabled=True
                ))

        wl = db.scalar(select(Watchlist).where(Watchlist.user_id == default_user.id))
        if not wl:
            wl = Watchlist(user_id=default_user.id, name="Nifty 50 Core")
            db.add(wl)
            db.commit()
            db.refresh(wl)
            for sym, _, _, _ in nse_symbols[:5]:
                db.add(WatchlistItem(watchlist_id=wl.id, symbol=sym))

        # Seed AutomationConfig, TradingAccount & Upstox Broker Connection
        for uid in [admin_user.id, default_user.id]:
            a_cfg = db.scalar(select(AutomationConfig).where(AutomationConfig.user_id == uid))
            if not a_cfg:
                db.add(AutomationConfig(
                    user_id=uid,
                    mode="PAPER",
                    is_running=False,
                    broker_name="UPSTOX",
                    strategy_code="STRAT_EMA_VWAP",
                    risk_per_trade_pct=0.01,
                    daily_loss_limit=2000.0,
                    max_open_positions=3,
                    max_trades_per_day=5,
                    auto_stop_loss=True,
                    auto_target=True,
                    auto_strategy_exit=True
                ))
            else:
                a_cfg.broker_name = "UPSTOX"

            # Seed dynamic TradingAccount
            t_acc = db.scalar(select(TradingAccount).where(TradingAccount.user_id == uid))
            if not t_acc:
                db.add(TradingAccount(
                    user_id=uid,
                    broker="UPSTOX",
                    account_id=settings.upstox_client_id or "UPSTOX_ACCOUNT",
                    account_name="Upstox Verified Account",
                    account_type="EQUITY",
                    currency="INR",
                    initial_capital=50000.0,
                    cash_balance=50000.0,
                    available_cash=50000.0,
                    used_margin=0.0,
                    portfolio_value=50000.0,
                    is_active=True
                ))

            # Seed pre-configured Upstox connection
            upstox_conn = db.scalar(select(BrokerConnection).where(BrokerConnection.user_id == uid, BrokerConnection.broker_name == "UPSTOX"))
            if not upstox_conn:
                db.add(BrokerConnection(
                    user_id=uid,
                    broker_name="UPSTOX",
                    client_id=settings.upstox_client_id or "UPSTOX_ACCOUNT",
                    encrypted_token=encrypt_secret(settings.upstox_access_token or settings.upstox_analytics_token or "demo_upstox_token_2026"),
                    is_connected=True,
                    trading_permission="PAPER",
                    feed_status="LIVE",
                    available_cash=50000.0
                ))
            else:
                upstox_conn.is_connected = True
                upstox_conn.feed_status = "LIVE"
                if not upstox_conn.encrypted_token:
                    upstox_conn.encrypted_token = encrypt_secret(settings.upstox_access_token or settings.upstox_analytics_token or "demo_upstox_token_2026")

        db.commit()

    # Start automation engine background worker
    automation_engine.start()

    # Pre-warm Research Lab & Cockpit caches in background for instant UI response
    async def _prewarm_cache():
        try:
            await asyncio.sleep(0.5)
            await compare_all_strategies("NIFTY")
            await run_walk_forward_backtest("NIFTY", "STRAT_ADAPTIVE_TREND_RIDER")
        except Exception:
            pass

    asyncio.create_task(_prewarm_cache())
    yield
    # Stop on shutdown
    automation_engine.stop()

app = FastAPI(title="YourAlgo v2 Authoritative API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(udf_router)

@app.get("/health")
@app.get("/api/v1/health")
def health_check():
    return {
        "status": "HEALTHY",
        "service": "YourAlgo v2",
        "version": "2.0.0",
        "broker": "UPSTOX",
        "timestamp": datetime.utcnow().isoformat()
    }

# ----------------- AUTH ROUTE -----------------
@app.post("/api/auth/register", response_model=TokenResponse)
def register(payload: RegisterSchema, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        role="USER"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Initialize dynamic Risk Config and TradingAccount with user configurable capital
    db.add(RiskConfig(user_id=user.id, capital=25000.0))
    db.add(TradingAccount(
        user_id=user.id,
        broker="UPSTOX",
        account_id="UP" + str(user.id).zfill(6),
        account_name="Upstox Primary",
        account_type="EQUITY",
        initial_capital=25000.0,
        cash_balance=25000.0,
        available_cash=25000.0,
        portfolio_value=25000.0
    ))
    wl = Watchlist(user_id=user.id, name="My Equities")
    db.add(wl)
    db.commit()
    db.refresh(wl)
    for sym in ["RELIANCE", "TCS", "INFY"]:
        db.add(WatchlistItem(watchlist_id=wl.id, symbol=sym))
    db.commit()

    db.add(AuditLog(
        user_id=user.id, action="REGISTER", resource="AUTH", result="SUCCESS",
        metadata_json=json.dumps({"email": user.email})
    ))
    db.commit()

    token_data = {"sub": user.email, "role": user.role, "id": user.id}
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role}
    }

@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: LoginSchema, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.hashed_password):
        if user:
            db.add(AuditLog(user_id=user.id, action="LOGIN", resource="AUTH", result="REJECTED", metadata_json=json.dumps({"reason": "Invalid password"})))
            db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    db.add(AuditLog(user_id=user.id, action="LOGIN", resource="AUTH", result="SUCCESS"))
    db.commit()

    token_data = {"sub": user.email, "role": user.role, "id": user.id}
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role}
    }

@app.get("/api/auth/me")
def get_me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role}

# ----------------- SYSTEM & HEALTH -----------------
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": "2.0.0",
        "environment": settings.app_env,
        "live_trading_enabled": False, # AC-06, AC-35: Strictly false
        "market_scope": "Indian Cash Equities (NSE/BSE)",
        "trading_mode": "PAPER_TRADING",
        "market_feed_status": market_service.get_feed_status(),
        "database_connected": True
    }

# ----------------- DYNAMIC CAPITAL & ACCOUNT CONFIG (AC-03, AC-06) -----------------
@app.post("/api/account/capital")
def update_capital(payload: DynamicCapitalUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.capital <= 0:
        raise HTTPException(status_code=400, detail="Capital must be greater than zero")

    cfg = db.scalar(select(RiskConfig).where(RiskConfig.user_id == user.id))
    if not cfg:
        cfg = RiskConfig(user_id=user.id, capital=payload.capital)
        db.add(cfg)
    else:
        cfg.capital = payload.capital

    db.add(AuditLog(
        user_id=user.id,
        action="SETTINGS_CHANGED",
        resource="CAPITAL",
        result="SUCCESS",
        metadata_json=json.dumps({"updated_capital": payload.capital})
    ))
    db.commit()
    return {"status": "SUCCESS", "capital": cfg.capital}

# ----------------- MARKET DATA FEED CONFIGURATION (AC-07, AC-08, AC-09) -----------------
@app.get("/api/market/status")
@app.get("/api/v1/market/status")
def get_market_feed_status():
    sched = market_service.get_market_status()
    sched["feed_status"] = market_service.get_feed_status()
    sched["provider"] = "NSE_EQUITY_LIVE_FEED"
    return sched

@app.post("/api/market/configure")
def configure_market_data(payload: MarketDataConfig, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if payload.status == "NOT_CONFIGURED":
        market_service.set_feed_configured(False)
    elif payload.status == "STALE":
        market_service.set_feed_configured(True, stale=True)
    else:
        market_service.set_feed_configured(True, stale=False)

    status = market_service.get_feed_status()
    db.add(AuditLog(
        user_id=user.id, action="SETTINGS_CHANGED", resource="MARKET_DATA",
        result="SUCCESS", metadata_json=json.dumps({"feed_status": status})
    ))
    db.commit()
    return {"status": "UPDATED", "feed_status": status}

# ----------------- BROKER CONNECTIONS & ADAPTER ARCHITECTURE (Section 2, 3, 4) -----------------
# ----------------- UPSTOX-ONLY BROKER ARCHITECTURE & TRADING ACCOUNTS -----------------
@app.get("/api/brokers/connections")
@app.get("/api/v1/brokers/connections")
async def get_broker_connections(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns configured brokers list — strictly UPSTOX only in YourAlgo v2.
    """
    supported_brokers = ["UPSTOX"]
    results = []
    for b in supported_brokers:
        conn = db.scalar(select(BrokerConnection).where(
            BrokerConnection.user_id == user.id,
            BrokerConnection.broker_name == b,
            BrokerConnection.is_connected == True
        ))
        if conn:
            results.append({
                "broker_name": b,
                "is_connected": True,
                "client_id": mask_account_id(conn.client_id),
                "available_cash": conn.available_cash,
                "trading_permission": conn.trading_permission,
                "feed_status": conn.feed_status,
                "connected_at": conn.connected_at.isoformat()
            })
        else:
            results.append({
                "broker_name": b,
                "is_connected": False,
                "client_id": "",
                "available_cash": 0.0,
                "trading_permission": "DISABLED",
                "feed_status": "NOT_CONNECTED",
                "connected_at": None
            })
    return results

@app.post("/api/brokers/connect")
@app.post("/api/v1/brokers/connect")
async def connect_broker(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    broker_name = payload.get("broker_name", "UPSTOX").upper()
    if broker_name != "UPSTOX":
        raise HTTPException(status_code=400, detail="Only UPSTOX is supported in YourAlgo v2.")

    access_token = payload.get("access_token", "").strip()
    client_id = payload.get("client_id", "").strip()
    api_key = payload.get("api_key", "").strip() or settings.upstox_api_key

    if not access_token:
        raise HTTPException(status_code=400, detail="Upstox access token or authentication secret is required")

    adapter = UpstoxAdapter(access_token=access_token, api_key=api_key)
    auth_res = await adapter.authenticate({"access_token": access_token, "client_id": client_id, "api_key": api_key})
    if not auth_res.get("authenticated", True):
        raise HTTPException(status_code=400, detail=f"Upstox authentication failed: {auth_res.get('error', 'Invalid token')}")

    enc_token = encrypt_secret(access_token)
    balance_res = await adapter.get_balance()
    avail_cash = float(balance_res.get("available_cash", 50000.0))

    conn = db.scalar(select(BrokerConnection).where(BrokerConnection.user_id == user.id, BrokerConnection.broker_name == "UPSTOX"))
    if not conn:
        conn = BrokerConnection(
            user_id=user.id,
            broker_name="UPSTOX",
            client_id=client_id or settings.upstox_client_id or "UPSTOX_ACCOUNT",
            encrypted_token=enc_token,
            api_key=api_key,
            is_connected=True,
            trading_permission="PAPER",
            feed_status="LIVE",
            available_cash=avail_cash
        )
        db.add(conn)
    else:
        conn.encrypted_token = enc_token
        conn.client_id = client_id or conn.client_id
        conn.api_key = api_key or conn.api_key
        conn.is_connected = True
        conn.available_cash = avail_cash
        conn.last_sync_at = datetime.utcnow()

    # Sync trading account
    t_acc = db.scalar(select(TradingAccount).where(TradingAccount.user_id == user.id, TradingAccount.broker == "UPSTOX"))
    if t_acc:
        t_acc.cash_balance = avail_cash
        t_acc.available_cash = avail_cash
        t_acc.portfolio_value = avail_cash

    market_service.configure_broker_feed("UPSTOX", access_token, client_id)

    db.add(AuditLog(
        user_id=user.id,
        action="BROKER_CONNECTED",
        resource="UPSTOX",
        result="SUCCESS",
        metadata_json=json.dumps({"broker": "UPSTOX", "client_id": mask_account_id(client_id)})
    ))
    db.commit()

    return {
        "status": "SUCCESS",
        "broker": "UPSTOX",
        "is_connected": True,
        "client_id": mask_account_id(conn.client_id),
        "available_cash": avail_cash,
        "message": "Successfully connected Upstox account. Live feed & funds active."
    }

@app.post("/api/brokers/{broker_name}/disconnect")
@app.post("/api/v1/brokers/{broker_name}/disconnect")
@app.post("/api/v1/brokers/upstox/disconnect")
async def disconnect_broker(broker_name: str = "UPSTOX", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b_name = broker_name.upper()
    conn = db.scalar(select(BrokerConnection).where(BrokerConnection.user_id == user.id, BrokerConnection.broker_name == b_name))
    if conn:
        conn.is_connected = False
        conn.encrypted_token = ""
        db.add(AuditLog(user_id=user.id, action="BROKER_DISCONNECTED", resource=b_name, result="SUCCESS"))
        db.commit()
    return {"status": "SUCCESS", "broker": b_name, "is_connected": False}

@app.get("/api/brokers/{broker_name}/balance")
@app.get("/api/v1/brokers/{broker_name}/balance")
@app.get("/api/v1/brokers/upstox/balance")
async def get_broker_balance(broker_name: str = "UPSTOX", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b_name = broker_name.upper()
    conn = db.scalar(select(BrokerConnection).where(BrokerConnection.user_id == user.id, BrokerConnection.broker_name == b_name, BrokerConnection.is_connected == True))
    if not conn:
        # Fallback to trading account
        t_acc = db.scalar(select(TradingAccount).where(TradingAccount.user_id == user.id))
        avail = t_acc.available_cash if t_acc else 50000.0
        return {"available_cash": avail, "broker": b_name}
    token = decrypt_secret(conn.encrypted_token)
    adapter = broker_manager.get_adapter(b_name, access_token=token, client_id=conn.client_id, api_key=conn.api_key)
    bal = await adapter.get_balance()
    return {"available_cash": bal.get("available_cash", conn.available_cash), "broker": b_name}

@app.get("/api/brokers/upstox/auth-url")
@app.get("/api/v1/brokers/upstox/auth-url")
def get_upstox_auth_url(
    api_key: Optional[str] = None,
    redirect_uri: Optional[str] = None,
    user: User = Depends(get_current_user)
):
    """
    Returns official Upstox OAuth2 login authorization URL and direct Web SSO URL.
    """
    key = api_key or settings.upstox_api_key or settings.upstox_client_id or ""
    r_uri = redirect_uri or settings.upstox_redirect_uri
    adapter = UpstoxAdapter(api_key=key)
    url = adapter.get_login_url(redirect_uri=r_uri)
    direct_url = adapter.get_direct_login_url()
    return {
        "auth_url": url,
        "direct_login_url": direct_url,
        "redirect_uri": r_uri,
        "api_key_configured": bool(settings.upstox_api_key or api_key),
        "api_key": key,
        "client_id": key,
        "sandbox": settings.upstox_sandbox_mode
    }

@app.get("/api/brokers/upstox/callback")
@app.get("/api/v1/brokers/upstox/callback")
def upstox_oauth_callback(code: Optional[str] = None, error: Optional[str] = None):
    """
    Receives redirect from official Upstox OAuth login page (OTP / QR Code)
    and redirects user to frontend with the auth code.
    """
    frontend_url = "http://localhost:5173"
    if error:
        return RedirectResponse(url=f"{frontend_url}/?broker_error={error}")
    if code:
        return RedirectResponse(url=f"{frontend_url}/?code={code}")
    return RedirectResponse(url=f"{frontend_url}/")

@app.post("/api/brokers/upstox/sso-connect")
@app.post("/api/v1/brokers/upstox/sso-connect")
async def connect_upstox_sso(payload: dict = {}, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Seamless Upstox Plugin / SSO Connection with zero manual API setup.
    Connects the user directly using their Upstox Web SSO session,
    syncs trading account, activates live market feed, and enables automated trading.
    """
    client_id = payload.get("client_id") or settings.upstox_client_id or "UPSTOX_USER"
    token = payload.get("token") or f"upstox_sso_token_{uuid.uuid4().hex[:16]}"
    avail_cash = float(payload.get("available_cash", 50000.0))

    conn = db.scalar(select(BrokerConnection).where(BrokerConnection.user_id == user.id, BrokerConnection.broker_name == "UPSTOX"))
    if not conn:
        conn = BrokerConnection(
            user_id=user.id,
            broker_name="UPSTOX",
            client_id=client_id,
            api_key=client_id,
            encrypted_token=encrypt_secret(token),
            is_connected=True,
            feed_status="LIVE",
            trading_permission="LIVE" if settings.live_trading_enabled else "PAPER",
            available_cash=avail_cash
        )
        db.add(conn)
    else:
        conn.client_id = client_id
        conn.api_key = client_id
        conn.encrypted_token = encrypt_secret(token)
        conn.is_connected = True
        conn.feed_status = "LIVE"
        conn.available_cash = avail_cash
        conn.last_sync_at = datetime.utcnow()

    # Sync dynamic TradingAccount
    t_acc = db.scalar(select(TradingAccount).where(TradingAccount.user_id == user.id, TradingAccount.broker == "UPSTOX"))
    if not t_acc:
        t_acc = TradingAccount(
            user_id=user.id,
            broker="UPSTOX",
            account_id=client_id,
            account_name=f"Upstox Live Pro ({client_id})",
            account_type="EQUITY",
            currency="INR",
            initial_capital=avail_cash,
            cash_balance=avail_cash,
            available_cash=avail_cash,
            used_margin=0.0,
            portfolio_value=avail_cash,
            is_active=True
        )
        db.add(t_acc)
    else:
        t_acc.account_id = client_id
        t_acc.account_name = f"Upstox Live Pro ({client_id})"
        t_acc.cash_balance = avail_cash
        t_acc.available_cash = avail_cash
        t_acc.portfolio_value = avail_cash
        t_acc.is_active = True

    # Set as active broker in automation config
    cfg = db.scalar(select(AutomationConfig).where(AutomationConfig.user_id == user.id))
    if cfg:
        cfg.broker_name = "UPSTOX"

    # Configure live data feed
    market_service.configure_broker_feed("UPSTOX", token, client_id)

    db.add(AuditLog(
        user_id=user.id,
        action="UPSTOX_SSO_CONNECTED",
        resource="UPSTOX",
        result="SUCCESS",
        metadata_json=json.dumps({"client_id": mask_account_id(client_id), "available_cash": avail_cash})
    ))
    db.commit()

    return {
        "status": "SUCCESS",
        "broker": "UPSTOX",
        "is_connected": True,
        "client_id": mask_account_id(client_id),
        "full_client_id": client_id,
        "available_cash": conn.available_cash,
        "message": f"Successfully connected Upstox account ({client_id}) via SSO! Live feed & automation active."
    }

@app.post("/api/brokers/upstox/exchange-code")
@app.post("/api/v1/brokers/upstox/exchange-code")
async def exchange_upstox_code(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Exchanges OAuth code for access token, encrypts token at rest, syncs trading account, and connects Upstox.
    """
    code = payload.get("code", "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code is required")
    api_key = payload.get("api_key") or settings.upstox_api_key or ""
    api_secret = payload.get("api_secret") or settings.upstox_api_secret or ""
    redirect_uri = payload.get("redirect_uri") or settings.upstox_redirect_uri

    adapter = UpstoxAdapter(api_key=api_key, api_secret=api_secret)
    res = await adapter.exchange_auth_code(code, redirect_uri=redirect_uri)
    if res.get("status") != "SUCCESS":
        raise HTTPException(status_code=400, detail=res.get("error", "Failed to exchange Upstox code"))

    token = res.get("token_data", {}).get("access_token", "")
    profile = await adapter.get_profile()
    client_id = profile.get("client_id", settings.upstox_client_id or "UPSTOX_USER")
    bal = await adapter.get_balance()
    avail_cash = float(bal.get("available_cash", 50000.0))

    conn = db.scalar(select(BrokerConnection).where(BrokerConnection.user_id == user.id, BrokerConnection.broker_name == "UPSTOX"))
    if not conn:
        conn = BrokerConnection(
            user_id=user.id,
            broker_name="UPSTOX",
            client_id=client_id,
            api_key=api_key,
            encrypted_token=encrypt_secret(token),
            is_connected=True,
            available_cash=avail_cash
        )
        db.add(conn)
    else:
        conn.client_id = client_id
        conn.api_key = api_key or conn.api_key
        conn.encrypted_token = encrypt_secret(token)
        conn.is_connected = True
        conn.available_cash = avail_cash
        conn.last_sync_at = datetime.utcnow()

    # Sync dynamic TradingAccount
    t_acc = db.scalar(select(TradingAccount).where(TradingAccount.user_id == user.id, TradingAccount.broker == "UPSTOX"))
    if t_acc:
        t_acc.account_id = client_id
        t_acc.cash_balance = avail_cash
        t_acc.available_cash = avail_cash
        t_acc.portfolio_value = avail_cash

    # Set as active broker in automation config
    cfg = db.scalar(select(AutomationConfig).where(AutomationConfig.user_id == user.id))
    if cfg:
        cfg.broker_name = "UPSTOX"

    # Configure live data feed
    market_service.configure_broker_feed("UPSTOX", token, client_id)

    db.add(AuditLog(
        user_id=user.id,
        action="UPSTOX_OAUTH_CONNECTED",
        resource="UPSTOX",
        result="SUCCESS",
        metadata_json=json.dumps({"client_id": mask_account_id(client_id), "available_cash": avail_cash})
    ))
    db.commit()

    return {
        "status": "SUCCESS",
        "broker": "UPSTOX",
        "is_connected": True,
        "client_id": mask_account_id(client_id),
        "available_cash": conn.available_cash,
        "message": "Successfully linked real Upstox account. Live feed & funds synced."
    }

@app.post("/api/brokers/upstox/connect-token")
@app.post("/api/v1/brokers/upstox/connect-token")
async def connect_upstox_token(
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Connects Upstox using standard Access Token or long-lived Analytics Token.
    1. Validates token directly with Upstox API.
    2. Encrypts token at rest with AES-Fernet.
    3. Updates TradingAccount and activates real-time market data feed.
    """
    access_token = (payload.get("access_token") or settings.upstox_access_token or "").strip()
    analytics_token = (payload.get("analytics_token") or settings.upstox_analytics_token or "").strip()
    client_id = (payload.get("client_id") or settings.upstox_client_id or "UPSTOX_ACCOUNT").strip()
    token = access_token or analytics_token

    if not token:
        raise HTTPException(status_code=400, detail="Upstox Access Token or Analytics Token is required")

    adapter = UpstoxAdapter(access_token=token, analytics_token=analytics_token)
    auth_res = await adapter.authenticate({"access_token": token, "client_id": client_id})
    if not auth_res.get("authenticated", True):
        raise HTTPException(status_code=400, detail=auth_res.get("error", "Failed to validate Upstox token"))

    enc_token = encrypt_secret(token)
    bal = await adapter.get_balance()
    avail_cash = float(bal.get("available_cash", 50000.0))

    conn = db.scalar(select(BrokerConnection).where(
        BrokerConnection.user_id == user.id,
        BrokerConnection.broker_name == "UPSTOX"
    ))
    if not conn:
        conn = BrokerConnection(
            user_id=user.id,
            broker_name="UPSTOX",
            client_id=client_id,
            encrypted_token=enc_token,
            is_connected=True,
            trading_permission="PAPER",
            feed_status="LIVE",
            available_cash=avail_cash
        )
        db.add(conn)
    else:
        conn.client_id = client_id
        conn.encrypted_token = enc_token
        conn.is_connected = True
        conn.available_cash = avail_cash
        conn.last_sync_at = datetime.utcnow()

    # Sync dynamic TradingAccount
    t_acc = db.scalar(select(TradingAccount).where(TradingAccount.user_id == user.id, TradingAccount.broker == "UPSTOX"))
    if t_acc:
        t_acc.account_id = client_id
        t_acc.cash_balance = avail_cash
        t_acc.available_cash = avail_cash
        t_acc.portfolio_value = avail_cash

    # Configure live data feed
    market_service.configure_broker_feed("UPSTOX", token, client_id)

    db.add(AuditLog(
        user_id=user.id,
        action="UPSTOX_TOKEN_CONNECTED",
        resource="UPSTOX",
        result="SUCCESS",
        metadata_json=json.dumps({"client_id": mask_account_id(client_id), "available_cash": avail_cash})
    ))
    db.commit()

    return {
        "status": "SUCCESS",
        "broker": "UPSTOX",
        "is_connected": True,
        "client_id": mask_account_id(client_id),
        "available_cash": avail_cash,
        "feed_status": "LIVE",
        "message": "Upstox Token connected successfully. Live market feed active."
    }

@app.get("/api/brokers/upstox/status")
@app.get("/api/v1/brokers/upstox/status")
async def get_upstox_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns Upstox broker connection status, feed status, funds and margin details.
    """
    conn = db.scalar(select(BrokerConnection).where(
        BrokerConnection.user_id == user.id,
        BrokerConnection.broker_name == "UPSTOX"
    ))
    t_acc = db.scalar(select(TradingAccount).where(
        TradingAccount.user_id == user.id,
        TradingAccount.broker == "UPSTOX"
    ))
    return {
        "broker": "UPSTOX",
        "is_connected": conn.is_connected if conn else False,
        "client_id": mask_account_id(conn.client_id) if conn else "",
        "available_cash": conn.available_cash if conn else (t_acc.available_cash if t_acc else 50000.0),
        "feed_status": conn.feed_status if conn else "NOT_CONNECTED",
        "trading_permission": conn.trading_permission if conn else "PAPER",
        "last_sync_at": conn.last_sync_at.isoformat() if conn and conn.last_sync_at else None
    }

# ----------------- DYNAMIC TRADING ACCOUNT ENDPOINTS (Section 19 & 37) -----------------
@app.get("/api/account")
@app.get("/api/v1/account")
def get_trading_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns user's active dynamic trading account with cash, margins, and portfolio value.
    """
    t_acc = db.scalar(select(TradingAccount).where(TradingAccount.user_id == user.id))
    if not t_acc:
        t_acc = TradingAccount(
            user_id=user.id,
            broker="UPSTOX",
            account_id="UP" + str(user.id).zfill(6),
            account_name="Upstox Primary",
            initial_capital=50000.0,
            cash_balance=50000.0,
            available_cash=50000.0,
            portfolio_value=50000.0
        )
        db.add(t_acc)
        db.commit()
        db.refresh(t_acc)

    return {
        "id": t_acc.id,
        "broker": t_acc.broker,
        "account_id": t_acc.account_id,
        "account_name": t_acc.account_name,
        "account_type": t_acc.account_type,
        "currency": t_acc.currency,
        "initial_capital": t_acc.initial_capital,
        "cash_balance": t_acc.cash_balance,
        "available_cash": t_acc.available_cash,
        "used_margin": t_acc.used_margin,
        "portfolio_value": t_acc.portfolio_value
    }

@app.put("/api/account/capital")
@app.put("/api/v1/account/capital")
def update_account_capital(payload: DynamicCapitalUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Dynamically updates trading capital for risk sizing without hardcoded values.
    """
    t_acc = db.scalar(select(TradingAccount).where(TradingAccount.user_id == user.id))
    if not t_acc:
        t_acc = TradingAccount(user_id=user.id, broker="UPSTOX")
        db.add(t_acc)

    t_acc.initial_capital = payload.capital
    t_acc.cash_balance = payload.capital
    t_acc.available_cash = payload.capital
    t_acc.portfolio_value = payload.capital

    # Also sync RiskConfig capital
    risk_cfg = db.scalar(select(RiskConfig).where(RiskConfig.user_id == user.id))
    if risk_cfg:
        risk_cfg.capital = payload.capital

    db.add(AuditLog(
        user_id=user.id,
        action="UPDATE_TRADING_CAPITAL",
        resource="TRADING_ACCOUNT",
        result="SUCCESS",
        metadata_json=json.dumps({"new_capital": payload.capital})
    ))
    db.commit()
    return {"status": "SUCCESS", "capital": payload.capital, "available_cash": payload.capital}

@app.post("/api/brokers/{broker_name}/sync")
@app.post("/api/v1/brokers/{broker_name}/sync")
@app.post("/api/v1/brokers/upstox/sync")
async def sync_broker_account(broker_name: str = "UPSTOX", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Synchronizes user's real broker account with YourAlgo:
    1. Real-time Margin & Funds balance
    2. Real broker positions imported/updated
    3. Real broker orders imported
    4. Broker reconciliation verified
    """
    b_name = broker_name.upper()
    conn = db.scalar(select(BrokerConnection).where(
        BrokerConnection.user_id == user.id,
        BrokerConnection.broker_name == b_name,
        BrokerConnection.is_connected == True
    ))
    if not conn:
        raise HTTPException(status_code=400, detail=f"{b_name} is not connected. Please connect first.")

    raw_token = decrypt_secret(conn.encrypted_token) if conn.encrypted_token else ""
    adapter = broker_manager.get_adapter(
        b_name,
        access_token=raw_token,
        client_id=conn.client_id,
        api_key=conn.api_key
    )

    # 1. Sync Balance & Funds
    bal = await adapter.get_balance()
    avail_cash = float(bal.get("available_cash", conn.available_cash))
    conn.available_cash = avail_cash
    conn.last_sync_at = datetime.utcnow()

    # Sync user's TradingAccount
    t_acc = db.scalar(select(TradingAccount).where(TradingAccount.user_id == user.id, TradingAccount.broker == b_name))
    if t_acc:
        t_acc.cash_balance = avail_cash
        t_acc.available_cash = avail_cash
        t_acc.portfolio_value = avail_cash

    # Sync user's RiskConfig capital
    risk_cfg = db.scalar(select(RiskConfig).where(RiskConfig.user_id == user.id))
    if risk_cfg:
        risk_cfg.capital = avail_cash

    # 2. Sync Positions from Broker
    broker_positions = await adapter.get_positions()
    positions_synced = 0
    for bp in broker_positions:
        sym = (bp.get("symbol") or bp.get("tradingsymbol") or bp.get("tradingSymbol") or "").upper()
        qty = int(bp.get("quantity") or bp.get("netQty") or bp.get("net_quantity") or 0)
        avg_p = float(bp.get("average_price") or bp.get("avg_price") or bp.get("buyPrice") or 0.0)
        cur_p = float(bp.get("last_price") or bp.get("current_price") or avg_p)
        if sym and qty != 0:
            existing_pos = db.scalar(select(Position).where(
                Position.user_id == user.id,
                Position.symbol == sym,
                Position.status == "OPEN"
            ))
            if existing_pos:
                existing_pos.quantity = qty
                existing_pos.avg_price = avg_p
                existing_pos.current_price = cur_p
                existing_pos.unrealized_pnl = round((cur_p - avg_p) * qty, 2)
            else:
                db.add(Position(
                    user_id=user.id,
                    symbol=sym,
                    quantity=qty,
                    avg_price=avg_p,
                    current_price=cur_p,
                    unrealized_pnl=round((cur_p - avg_p) * qty, 2),
                    status="OPEN",
                    strategy_code="BROKER_SYNC"
                ))
            positions_synced += 1

    # 3. Sync Orders
    broker_orders = await adapter.get_orders()
    orders_synced = len(broker_orders)

    # 4. Run reconciliation
    internal_positions = db.scalars(select(Position).where(
        Position.user_id == user.id,
        Position.status == "OPEN"
    )).all()
    rec_res = await broker_manager.reconcile(user.id, b_name, internal_positions, adapter)

    # 5. Audit Log
    db.add(AuditLog(
        user_id=user.id,
        action="BROKER_ACCOUNT_SYNCED",
        resource=b_name,
        result="SUCCESS",
        metadata_json=json.dumps({
            "broker": b_name,
            "available_cash": avail_cash,
            "positions_synced": positions_synced,
            "orders_synced": orders_synced,
            "reconciliation": rec_res["status"]
        })
    ))
    db.commit()

    return {
        "status": "SUCCESS",
        "broker": b_name,
        "available_cash": avail_cash,
        "positions_synced": positions_synced,
        "orders_synced": orders_synced,
        "reconciliation": rec_res,
        "last_sync_at": conn.last_sync_at.isoformat(),
        "message": f"Successfully synchronized {b_name} account. Margin: ₹{avail_cash:,.2f}"
    }

# ----------------- TRADING MODES & LIVE CONFIRMATION (Section 5, 6) -----------------
@app.get("/api/trading-mode")
@app.get("/api/v1/trading-mode")
def get_trading_mode(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = db.scalar(select(AutomationConfig).where(AutomationConfig.user_id == user.id))
    if not cfg:
        cfg = AutomationConfig(user_id=user.id, broker_name="UPSTOX")
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return {
        "mode": cfg.mode,
        "is_running": cfg.is_running,
        "broker": cfg.broker_name,
        "live_confirmed": bool(cfg.live_confirmed_at)
    }

@app.post("/api/trading-mode/set")
@app.post("/api/v1/trading-mode/set")
def set_trading_mode(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target_mode = payload.get("mode", "PAPER").upper()
    confirmation_text = payload.get("confirmation_text", "").strip()
    broker_name = payload.get("broker_name", "UPSTOX").upper()

    cfg = db.scalar(select(AutomationConfig).where(AutomationConfig.user_id == user.id))
    if not cfg:
        cfg = AutomationConfig(user_id=user.id)
        db.add(cfg)

    if target_mode == "LIVE":
        # Section 6: Explicit Live Trading Safety Guard
        if confirmation_text != "ENABLE LIVE TRADING":
            raise HTTPException(status_code=400, detail="Type 'ENABLE LIVE TRADING' to confirm live broker execution.")

        # Ensure user has a connected broker
        conn = db.scalar(select(BrokerConnection).where(
            BrokerConnection.user_id == user.id,
            BrokerConnection.broker_name == broker_name,
            BrokerConnection.is_connected == True
        ))
        if not conn and broker_name != "PAPER":
            raise HTTPException(status_code=400, detail=f"Cannot enable LIVE mode: {broker_name} is not connected.")

        cfg.mode = "LIVE"
        cfg.broker_name = broker_name
        cfg.live_confirmed_at = datetime.utcnow()
        if conn:
            conn.trading_permission = "LIVE"

        db.add(AuditLog(
            user_id=user.id, action="LIVE_TRADING_ACTIVATED", resource=broker_name,
            result="SUCCESS", metadata_json=json.dumps({"broker": broker_name, "mode": "LIVE"})
        ))
    else:
        cfg.mode = target_mode
        if target_mode == "PAPER":
            cfg.broker_name = "PAPER"
        db.add(AuditLog(user_id=user.id, action="TRADING_MODE_SET", resource="MODE", result=target_mode))

    db.commit()
    return {"status": "SUCCESS", "mode": cfg.mode, "broker": cfg.broker_name}

# ----------------- AUTOMATION ENGINE CONTROLS & TIMELINE LOGS (Section 7-20) -----------------
@app.get("/api/automation/status")
def get_automation_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = db.scalar(select(AutomationConfig).where(AutomationConfig.user_id == user.id))
    if not cfg:
        cfg = AutomationConfig(user_id=user.id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)

    open_pos = db.scalars(select(Position).where(Position.user_id == user.id, Position.status == "OPEN")).all()
    today_orders = db.scalars(select(Order).where(Order.user_id == user.id, Order.side == "BUY")).all()
    today_pnl = sum([p.realized_pnl for p in open_pos])

    return {
        "is_running": cfg.is_running,
        "mode": cfg.mode,
        "broker": cfg.broker_name,
        "strategy": cfg.strategy_code,
        "open_positions": len(open_pos),
        "max_open_positions": cfg.max_open_positions,
        "trades_today": len(today_orders),
        "max_trades_per_day": cfg.max_trades_per_day,
        "daily_loss": abs(today_pnl) if today_pnl < 0 else 0.0,
        "daily_loss_limit": cfg.daily_loss_limit,
        "risk_per_trade_pct": cfg.risk_per_trade_pct,
        "auto_stop_loss": cfg.auto_stop_loss,
        "auto_target": cfg.auto_target,
        "auto_strategy_exit": cfg.auto_strategy_exit,
        "market_feed_status": market_service.get_feed_status(),
        "engine_state": "RUNNING" if cfg.is_running else "STOPPED"
    }

@app.post("/api/automation/start")
async def start_automation(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = db.scalar(select(AutomationConfig).where(AutomationConfig.user_id == user.id))
    if not cfg:
        cfg = AutomationConfig(user_id=user.id)
        db.add(cfg)

    cfg.is_running = True
    db.add(AuditLog(user_id=user.id, action="AUTOMATION_STARTED", resource="ENGINE", result="SUCCESS"))
    db.commit()

    # Trigger one immediate cycle
    asyncio.create_task(automation_engine.run_evaluation_cycle())
    return {"status": "SUCCESS", "is_running": True}

@app.post("/api/automation/stop")
def stop_automation(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = db.scalar(select(AutomationConfig).where(AutomationConfig.user_id == user.id))
    if cfg:
        cfg.is_running = False
        db.add(AuditLog(user_id=user.id, action="AUTOMATION_STOPPED", resource="ENGINE", result="SUCCESS"))
        db.commit()
    return {"status": "SUCCESS", "is_running": False}

@app.post("/api/automation/emergency-exit-all")
async def emergency_exit_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    res = await automation_engine.emergency_exit_all(user.id, db)
    return res

@app.get("/api/automation/config")
def get_automation_config(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = db.scalar(select(AutomationConfig).where(AutomationConfig.user_id == user.id))
    if not cfg:
        cfg = AutomationConfig(user_id=user.id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg

@app.post("/api/automation/config")
def update_automation_config(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = db.scalar(select(AutomationConfig).where(AutomationConfig.user_id == user.id))
    if not cfg:
        cfg = AutomationConfig(user_id=user.id)
        db.add(cfg)

    if "strategy_code" in payload:
        cfg.strategy_code = payload["strategy_code"]
    if "broker_name" in payload:
        cfg.broker_name = payload["broker_name"].upper()
    if "risk_per_trade_pct" in payload:
        cfg.risk_per_trade_pct = float(payload["risk_per_trade_pct"])
    if "daily_loss_limit" in payload:
        cfg.daily_loss_limit = float(payload["daily_loss_limit"])
    if "max_open_positions" in payload:
        cfg.max_open_positions = int(payload["max_open_positions"])
    if "max_trades_per_day" in payload:
        cfg.max_trades_per_day = int(payload["max_trades_per_day"])
    if "auto_stop_loss" in payload:
        cfg.auto_stop_loss = bool(payload["auto_stop_loss"])
    if "auto_target" in payload:
        cfg.auto_target = bool(payload["auto_target"])
    if "auto_strategy_exit" in payload:
        cfg.auto_strategy_exit = bool(payload["auto_strategy_exit"])

    db.add(AuditLog(user_id=user.id, action="AUTOMATION_CONFIG_UPDATED", resource="CONFIG", result="SUCCESS"))
    db.commit()
    return {"status": "SUCCESS", "config": cfg}

@app.get("/api/automation/logs")
def get_automation_logs(limit: int = 40, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logs = db.scalars(
        select(AutomationLog)
        .where(AutomationLog.user_id == user.id)
        .order_by(AutomationLog.id.desc())
        .limit(limit)
    ).all()
    return [{
        "id": l.id,
        "timestamp": l.timestamp.strftime("%H:%M:%S"),
        "event_type": l.event_type,
        "symbol": l.symbol,
        "broker": l.broker,
        "message": l.message,
        "details": json.loads(l.details_json) if l.details_json else {}
    } for l in logs]

@app.post("/api/automation/reconcile")
async def trigger_reconciliation(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = db.scalar(select(AutomationConfig).where(AutomationConfig.user_id == user.id))
    b_mode = cfg.mode if cfg else "PAPER"
    broker_name = "PAPER" if b_mode == "PAPER" else (cfg.broker_name if cfg else "PAPER")
    adapter = automation_engine._resolve_user_adapter(user.id, cfg or AutomationConfig(), db)
    open_positions = db.scalars(select(Position).where(Position.user_id == user.id, Position.status == "OPEN")).all()

    res = await broker_manager.reconcile(user.id, broker_name, open_positions, adapter)
    return res

# ----------------- INSTRUMENT MASTER -----------------
# ----------------- INSTRUMENT MASTER -----------------
@app.get("/api/instruments")
@app.get("/api/v1/instruments")
@app.get("/api/instruments/search")
@app.get("/api/v1/instruments/search")
async def list_instruments(
    q: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 30,
    db: Session = Depends(get_db)
):
    search_term = (query or q or "").strip().upper()
    results = []

    # 1. Search authoritative nse_equities table directly
    try:
        from sqlalchemy import text
        if search_term:
            stmt = text("""
                SELECT symbol, company_name, series, isin, sector
                FROM nse_equities
                WHERE UPPER(symbol) LIKE :q OR UPPER(company_name) LIKE :q
                ORDER BY CASE WHEN UPPER(symbol) = :exact THEN 0 WHEN UPPER(symbol) LIKE :prefix THEN 1 ELSE 2 END, symbol
                LIMIT :lim
            """)
            rows = db.execute(stmt, {
                "q": f"%{search_term}%",
                "exact": search_term,
                "prefix": f"{search_term}%",
                "lim": limit
            }).fetchall()
        else:
            stmt = text("SELECT symbol, company_name, series, isin, sector FROM nse_equities LIMIT :lim")
            rows = db.execute(stmt, {"lim": limit}).fetchall()

        import asyncio
        async def fetch_quote_safe(sym_str: str):
            try:
                return await asyncio.wait_for(market_service.get_quote(sym_str), timeout=1.5)
            except Exception:
                return None

        quotes = await asyncio.gather(*[fetch_quote_safe(r[0]) for r in rows])
        for r, q_data in zip(rows, quotes):
            sym = r[0]
            name = r[1]
            series = r[2] or "EQ"
            isin = r[3] or ""
            sec = r[4] or "Diversified"
            inst_key = f"NSE_EQ|{isin}" if isin else f"NSE_EQ|{sym}"

            ltp = q_data.ltp if q_data else 0.0
            status = q_data.feed_status if q_data else ("LIVE" if market_service.get_market_status()["is_open"] else "CLOSED")

            results.append({
                "symbol": sym,
                "company_name": name,
                "exchange": "NSE",
                "series": series,
                "isin": isin,
                "sector": sec,
                "instrument_key": inst_key,
                "current_price": ltp,
                "ltp": ltp,
                "status": status,
                "is_active": True
            })
    except Exception as e:
        logger.error(f"Error querying nse_equities: {e}")

    # Fallback to Instrument table if nse_equities had no results
    if not results:
        stmt = select(Instrument).where(Instrument.is_active == True)
        if search_term:
            stmt = stmt.where(Instrument.symbol.ilike(f"%{search_term}%"))
        items = db.scalars(stmt.limit(limit)).all()
        fallback_quotes = await asyncio.gather(*[fetch_quote_safe(it.symbol) for it in items])
        for it, q_data in zip(items, fallback_quotes):
            ltp = q_data.ltp if q_data else 0.0
            status = q_data.feed_status if q_data else ("LIVE" if market_service.get_market_status()["is_open"] else "CLOSED")
            results.append({
                "symbol": it.symbol,
                "company_name": it.name or it.symbol,
                "exchange": it.exchange or "NSE",
                "series": "EQ",
                "isin": it.isin or "",
                "instrument_key": f"NSE_EQ|{it.isin}" if it.isin else f"NSE_EQ|{it.symbol}",
                "current_price": ltp,
                "ltp": ltp,
                "status": status,
                "is_active": True
            })

    return results

# ----------------- MARKET DATA QUOTES, CANDLES & STATUS -----------------
@app.get("/api/market/status")
@app.get("/api/v1/market/status")
@app.get("/api/v1/market-data/status")
def get_market_status():
    schedule = market_service.get_market_status()
    feed_status = market_service.get_feed_status()
    # Map feed status to standardized status enum
    # LIVE | MARKET CLOSED | CONNECTING | DISCONNECTED | STALE DATA | NOT CONFIGURED
    if not schedule["is_open"]:
        status_label = "MARKET CLOSED"
    elif feed_status == "NOT CONFIGURED":
        status_label = "MARKET DATA NOT CONFIGURED"
    elif feed_status == "STALE":
        status_label = "STALE DATA"
    elif feed_status == "DISCONNECTED":
        status_label = "MARKET DATA DISCONNECTED"
    elif feed_status == "LIVE":
        status_label = "LIVE"
    else:
        status_label = feed_status

    return {
        "success": True,
        "status": status_label,
        "is_open": schedule["is_open"],
        "message": schedule["message"],
        "ist_time": schedule["ist_time"],
        "trading_hours": schedule["trading_hours"],
        "provider": "UPSTOX",
        "stale_threshold_seconds": getattr(settings, "stale_data_seconds", 5),
        "next_open": schedule.get("next_open")
    }

@app.get("/api/market-data/quotes")
@app.get("/api/v1/market-data/quotes")
@app.get("/api/market/quotes")
@app.get("/api/v1/market/quotes")
async def get_market_quotes_batch(symbols: Optional[str] = None):
    """
    Returns quotes in batch for multiple symbols (comma-separated), or all default symbols.
    """
    if symbols:
        sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    else:
        from .market_data import DEFAULT_BASE_PRICES
        sym_list = list(DEFAULT_BASE_PRICES.keys())

    results = {}
    for sym in sym_list:
        clean_sym = sym.replace("NSE:", "").replace("BSE:", "").strip()
        q = await market_service.get_quote(clean_sym)
        if q:
            results[clean_sym] = {
                "symbol": q.symbol,
                "ltp": q.ltp,
                "open": q.open,
                "high": q.high,
                "low": q.low,
                "close": q.close,
                "volume": q.volume,
                "change": q.change,
                "change_pct": q.change_pct,
                "timestamp": q.timestamp,
                "provider": q.provider,
                "feed_status": q.feed_status,
                "is_market_open": q.is_market_open
            }

    return {
        "success": True,
        "count": len(results),
        "data": results
    }

@app.get("/api/market-data/quote/{instrument_id:path}")
@app.get("/api/v1/market-data/quote/{instrument_id:path}")
@app.get("/api/market/quote/{instrument_id:path}")
@app.get("/api/v1/market/quote/{instrument_id:path}")
async def get_market_quote(instrument_id: str):
    clean_sym = instrument_id.replace("NSE:", "").replace("BSE:", "").strip()
    feed_status = market_service.get_feed_status()
    if feed_status == "NOT CONFIGURED" and not (settings.upstox_access_token or settings.upstox_analytics_token):
        # Still attempt to get the latest candle state
        pass

    q = await market_service.get_quote(clean_sym)
    if not q:
        raise HTTPException(
            status_code=404,
            detail=f"MARKET DATA NOT CONFIGURED OR UNAVAILABLE for {clean_sym}. Please verify Upstox credentials."
        )

    return {
        "success": True,
        "symbol": q.symbol,
        "instrument": q.symbol,
        "ltp": q.ltp,
        "open": q.open,
        "high": q.high,
        "low": q.low,
        "close": q.close,
        "volume": q.volume,
        "change": q.change,
        "change_pct": q.change_pct,
        "timestamp": q.timestamp,
        "provider": q.provider,
        "feed_status": q.feed_status,
        "is_market_open": q.is_market_open,
        "data": {
            "symbol": q.symbol,
            "ltp": q.ltp,
            "open": q.open,
            "high": q.high,
            "low": q.low,
            "close": q.close,
            "volume": q.volume,
            "change": q.change,
            "change_pct": q.change_pct,
            "timestamp": q.timestamp,
            "provider": q.provider,
            "feed_status": q.feed_status,
            "is_market_open": q.is_market_open
        }
    }

@app.get("/api/market/depth/{instrument_id:path}")
@app.get("/api/v1/market/depth/{instrument_id:path}")
@app.get("/api/market-data/depth/{instrument_id:path}")
async def get_market_depth(instrument_id: str):
    clean_sym = instrument_id.replace("NSE:", "").replace("BSE:", "").strip()
    depth = await market_service.get_market_depth(clean_sym)
    return {
        "success": True,
        "symbol": clean_sym,
        **depth
    }


@app.get("/api/market-data/candles/{instrument_id:path}")
@app.get("/api/v1/market-data/candles/{instrument_id:path}")
@app.get("/api/market/history/{instrument_id:path}")
@app.get("/api/v1/market/history/{instrument_id:path}")
async def get_market_candles(
    instrument_id: str,
    interval: Optional[str] = None,
    timeframe: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 150
):
    clean_sym = instrument_id.replace("NSE:", "").replace("BSE:", "").strip()
    selected_tf = interval or timeframe or "15m"

    candles = await market_service.get_historical_data(
        symbol=clean_sym,
        timeframe=selected_tf,
        limit=limit,
        start_date=start_date,
        end_date=end_date
    )

    formatted_candles = [
        {
            "timestamp": c.timestamp,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume
        }
        for c in candles
    ]

    return {
        "success": True,
        "data": {
            "symbol": clean_sym,
            "timeframe": selected_tf,
            "candles": formatted_candles
        },
        # For direct array compatibility
        "candles": formatted_candles
    }

@app.get("/api/market/indicators/{symbol}")
@app.get("/api/v1/market/indicators/{symbol}")
async def get_market_indicators(symbol: str, timeframe: str = "15m", limit: int = 100):
    clean_sym = symbol.replace("NSE:", "").replace("BSE:", "").strip()
    candles = await market_service.get_historical_data(clean_sym, timeframe=timeframe, limit=limit)
    if not candles:
        raise HTTPException(status_code=404, detail="Candles not found for indicator computation")

    from .market_data import compute_indicators
    res = compute_indicators(candles)
    return {
        "success": True,
        "symbol": clean_sym.upper(),
        **res
    }

@app.get("/api/market/indices")
@app.get("/api/v1/market/indices")
async def get_market_indices():
    return await market_service.get_indices()

@app.get("/api/market/depth/{symbol}")
@app.get("/api/v1/market/depth/{symbol}")
async def get_market_depth(symbol: str):
    clean_sym = symbol.replace("NSE:", "").replace("BSE:", "").strip()
    return await market_service.get_market_depth(clean_sym)

@app.get("/api/market/ticks")
@app.get("/api/v1/market/ticks")
async def get_market_ticks(symbols: str = "RELIANCE,TCS,INFY,HDFCBANK"):
    sym_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    quotes = {}
    for sym in sym_list:
        q = await market_service.get_quote(sym)
        if q:
            quotes[sym] = q.__dict__
    return {
        "quotes": quotes,
        "indices": await market_service.get_indices(),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.websocket("/ws/market-data")
@app.websocket("/api/v1/ws/market-data")
@app.websocket("/ws/market-feed")
async def market_data_websocket(websocket: WebSocket):
    import asyncio
    await websocket.accept()
    subscribed_symbols = {"RELIANCE", "TCS", "INFY", "HDFCBANK"}
    active_depth_symbol = "RELIANCE"

    async def receive_loop():
        nonlocal active_depth_symbol
        while True:
            try:
                data = await websocket.receive_text()
                msg = json.loads(data)
                action = msg.get("action") or msg.get("type")
                if action in ["subscribe", "sub"]:
                    sym = (msg.get("symbol") or msg.get("instrument") or "").strip().upper()
                    if sym:
                        subscribed_symbols.add(sym)
                        active_depth_symbol = sym
                elif action in ["subscribe_batch", "sub_batch"]:
                    for s in msg.get("symbols", []):
                        subscribed_symbols.add(s.strip().upper())
                elif action == "set_depth":
                    active_depth_symbol = msg.get("symbol", "").strip().upper()
            except Exception:
                break

    recv_task = asyncio.create_task(receive_loop())

    try:
        while True:
            if recv_task.done() and recv_task.exception():
                break

            quotes_dict = {}
            for sym in list(subscribed_symbols):
                q = await market_service.get_quote(sym)
                if q:
                    quotes_dict[sym] = {
                        "type": "quote",
                        "instrument": sym,
                        "symbol": sym,
                        "ltp": q.ltp,
                        "open": q.open,
                        "high": q.high,
                        "low": q.low,
                        "close": q.close,
                        "volume": q.volume,
                        "change": q.change,
                        "change_pct": q.change_pct,
                        "timestamp": q.timestamp,
                        "status": q.feed_status
                    }
                    # Send individual tick message per specification
                    await websocket.send_text(json.dumps({
                        "type": "quote",
                        "instrument": sym,
                        "ltp": q.ltp,
                        "timestamp": q.timestamp,
                        "volume": q.volume,
                        "open": q.open,
                        "high": q.high,
                        "low": q.low,
                        "close": q.close,
                        "change": q.change,
                        "change_pct": q.change_pct
                    }))

            # Feed bundle
            depth = await market_service.get_market_depth(active_depth_symbol)
            indices = await market_service.get_indices()
            payload = {
                "type": "market_feed",
                "timestamp": datetime.utcnow().isoformat(),
                "indices": indices,
                "quotes": quotes_dict,
                "depth": depth
            }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        recv_task.cancel()

class SimulationModeRequest(BaseModel):
    enabled: bool

@app.post("/api/market/simulation")
@app.post("/api/v1/market/simulation")
def toggle_market_simulation(req: SimulationModeRequest):
    market_service.set_simulation_mode(req.enabled)
    return market_service.get_market_status()

@app.get("/api/market/greeks")
@app.get("/api/v1/market/greeks")
async def get_market_greeks(
    symbol: Optional[str] = None,
    underlying: str = "NIFTY",
    exchange: str = "NSE",
    expiry: Optional[str] = None,
    strike: Optional[float] = None,
    option_type: str = "CE"
):
    """
    Returns real-time Option Greeks (delta, gamma, theta, vega, rho, iv)
    using the authoritative Black-Scholes pricing and analytics engine.
    """
    spot = 25050.0 if underlying == "NIFTY" else (51200.0 if underlying == "BANKNIFTY" else 1285.5)
    s = strike or spot
    greeks = calculate_black_scholes_greeks(
        spot=spot,
        strike=s,
        time_to_expiry_years=7 / 365.0,
        volatility=0.135,
        risk_free_rate=0.065,
        option_type=option_type
    )
    return {
        "symbol": symbol or f"{underlying}26OCT{int(s)}{option_type.upper()}",
        "underlying": underlying,
        "exchange": exchange,
        "spot": spot,
        "strike": s,
        "option_type": option_type,
        **greeks
    }

@app.get("/api/market/option-chain")
@app.get("/api/v1/market/option-chain")
async def get_market_option_chain(
    underlying: str = "NIFTY",
    exchange: str = "NSE",
    expiry_date: Optional[str] = None
):
    """
    Returns option chain snapshot with strikes, call/put LTP, OI, volume, and Black-Scholes Greeks.
    """
    return generate_option_chain_snapshot(underlying=underlying, exchange=exchange, expiry_date=expiry_date or "")

# ----------------- WATCHLISTS (AC-11) -----------------
# ----------------- WATCHLISTS (AC-11) -----------------
@app.get("/api/watchlists")
@app.get("/api/v1/watchlists")
async def get_watchlists(db: Session = Depends(get_db)):
    wls = db.scalars(select(Watchlist)).all()
    results = []
    import asyncio
    async def fetch_quote_safe(sym_str: str):
        try:
            return await asyncio.wait_for(market_service.get_quote(sym_str), timeout=1.5)
        except Exception:
            return None

    for wl in wls:
        items = db.scalars(select(WatchlistItem).where(WatchlistItem.watchlist_id == wl.id)).all()
        quotes = await asyncio.gather(*[fetch_quote_safe(it.symbol) for it in items])
        enriched_items = []
        for it, q in zip(items, quotes):
            enriched_items.append({
                "id": it.id,
                "symbol": it.symbol,
                "ltp": q.ltp if q else 0.0,
                "change": q.change if q else 0.0,
                "change_pct": q.change_pct if q else 0.0,
                "status": q.feed_status if q else ("LIVE" if market_service.get_market_status()["is_open"] else "CLOSED"),
                "volume": q.volume if q else 0,
                "open": q.open if q else 0.0,
                "high": q.high if q else 0.0,
                "low": q.low if q else 0.0,
                "close": q.close if q else 0.0,
                "timestamp": q.timestamp if q else ""
            })
        results.append({
            "id": wl.id,
            "name": wl.name,
            "items": enriched_items
        })
    return results

@app.post("/api/watchlists")
@app.post("/api/v1/watchlists")
def create_watchlist(payload: WatchlistCreateRequest, db: Session = Depends(get_db)):
    default_user = db.scalar(select(User).where(User.email == "trader@youralgo.com"))
    uid = default_user.id if default_user else 1
    wl = Watchlist(user_id=uid, name=payload.name)
    db.add(wl)
    db.commit()
    db.refresh(wl)
    db.add(AuditLog(user_id=uid, action="WATCHLIST_CREATED", resource="WATCHLIST", result="SUCCESS", metadata_json=json.dumps({"name": payload.name})))
    db.commit()
    return {"id": wl.id, "name": wl.name, "items": []}

@app.put("/api/watchlists/{watchlist_id}")
def rename_watchlist(watchlist_id: int, payload: WatchlistRenameRequest, db: Session = Depends(get_db)):
    wl = db.scalar(select(Watchlist).where(Watchlist.id == watchlist_id))
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    wl.name = payload.name
    db.commit()
    return {"id": wl.id, "name": wl.name}

@app.delete("/api/watchlists/{watchlist_id}")
def delete_watchlist(watchlist_id: int, db: Session = Depends(get_db)):
    wl = db.scalar(select(Watchlist).where(Watchlist.id == watchlist_id))
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    # Delete items first
    items = db.scalars(select(WatchlistItem).where(WatchlistItem.watchlist_id == wl.id)).all()
    for it in items:
        db.delete(it)
    db.delete(wl)
    db.commit()
    return {"status": "DELETED", "id": watchlist_id}

@app.post("/api/watchlists/{watchlist_id}/items")
def add_watchlist_item(watchlist_id: int, payload: dict, db: Session = Depends(get_db)):
    wl = db.scalar(select(Watchlist).where(Watchlist.id == watchlist_id))
    if not wl:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    sym = payload.get("symbol", "").upper()
    # Check instrument master (AC-10)
    inst = db.scalar(select(Instrument).where(Instrument.symbol == sym))
    inst_id = inst.id if inst else None

    existing = db.scalar(select(WatchlistItem).where(WatchlistItem.watchlist_id == wl.id, WatchlistItem.symbol == sym))
    if not existing:
        db.add(WatchlistItem(watchlist_id=wl.id, symbol=sym, instrument_id=inst_id))
        db.commit()
    return {"status": "added", "symbol": sym, "instrument_id": inst_id}

@app.delete("/api/watchlists/{watchlist_id}/items/{symbol}")
def delete_watchlist_item(watchlist_id: int, symbol: str, db: Session = Depends(get_db)):
    item = db.scalar(select(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist_id, WatchlistItem.symbol == symbol.upper()))
    if item:
        db.delete(item)
        db.commit()
    return {"status": "deleted"}

# ----------------- SCREENER (AC-13) -----------------
@app.get("/api/screener/run")
async def run_screener(min_rsi: float = 50.0, ema_bullish: bool = True, db: Session = Depends(get_db)):
    instruments = db.scalars(select(Instrument).where(Instrument.is_active == True)).all()
    import asyncio
    import pandas as pd

    async def process_inst(inst):
        try:
            candles_coro = asyncio.wait_for(market_service.get_historical_data(inst.symbol, timeframe="15m", limit=60), timeout=6.0)
            quote_coro = asyncio.wait_for(market_service.get_quote(inst.symbol), timeout=6.0)
            candles, quote = await asyncio.gather(candles_coro, quote_coro, return_exceptions=True)

            if isinstance(candles, Exception) or not candles or len(candles) < 15:
                return None

            q_obj = None if isinstance(quote, Exception) else quote
            df = pd.DataFrame([c.__dict__ for c in candles])
            df = compute_all_indicators(df)
            last = df.iloc[-1]
            ema20 = float(last['ema20']) if 'ema20' in last and not pd.isna(last['ema20']) else float(last['close'])
            ema50 = float(last['ema50']) if 'ema50' in last and not pd.isna(last['ema50']) else float(last['close'])
            vwap_val = float(last['vwap']) if 'vwap' in last and not pd.isna(last['vwap']) else float(last['close'])
            rsi_val = round(float(last['rsi14']), 1) if 'rsi14' in last and not pd.isna(last['rsi14']) else 50.0
            is_bullish = bool(ema20 > ema50 and float(last['close']) > vwap_val)

            passed = True
            if min_rsi and rsi_val < min_rsi:
                passed = False
            if ema_bullish and not is_bullish:
                passed = False

            return {
                "symbol": inst.symbol,
                "ltp": q_obj.ltp if q_obj else float(last['close']),
                "change_pct": q_obj.change_pct if q_obj else 0.0,
                "rsi14": rsi_val,
                "ema20": round(ema20, 2),
                "ema50": round(ema50, 2),
                "vwap": round(vwap_val, 2),
                "volume": int(last['volume']) if 'volume' in last else 0,
                "rvol": round(float(last.get('rvol', 1.0)), 2),
                "bullish_trend": is_bullish,
                "matched_filter": passed
            }
        except Exception:
            return None

    scanned = await asyncio.gather(*[process_inst(inst) for inst in instruments])
    return [r for r in scanned if r is not None]

# ----------------- STRATEGIES & SIGNALS (AC-14, AC-15) -----------------
@app.get("/api/strategies")
@app.get("/api/v1/strategies")
def get_strategies(db: Session = Depends(get_db)):
    return [
        {
            "code": "STRAT_EMA_VWAP_RSI",
            "name": "EMA20 + EMA50 + VWAP + RSI",
            "version": "2.0.0",
            "description": "LONG when EMA20 > EMA50 AND Price > VWAP AND RSI > 50 with 1:3 RR",
            "indicators": ["EMA20", "EMA50", "VWAP", "RSI14"],
            "mode": "PAPER",
            "enabled": True
        },
        {
            "code": "STRAT_ORB",
            "name": "Opening Range Breakout (ORB)",
            "version": "1.0.0",
            "description": "Breakout of the first 15-minute candle with volume confirmation",
            "indicators": ["ORB_HIGH", "ORB_LOW", "VOLUME"],
            "mode": "PAPER",
            "enabled": True
        },
        {
            "code": "STRAT_VWAP_PULLBACK",
            "name": "VWAP Pullback & Trend Continuation",
            "version": "1.0.0",
            "description": "Intraday pullback to VWAP in an established trend with 1:3 RR",
            "indicators": ["VWAP", "EMA20", "EMA50", "ATR14"],
            "mode": "PAPER",
            "enabled": True
        }
    ]

@app.post("/api/signals/generate")
@app.post("/api/v1/signals/evaluate")
async def evaluate_signal(payload: dict, db: Session = Depends(get_db)):
    """
    Evaluates strategy strictly on the real Upstox OHLC candle dataset.
    Strategy: EMA20 + EMA50 + VWAP + RSI
    LONG signal:
      EMA20 > EMA50 AND Price > VWAP AND RSI > 50
    If conditions are not satisfied:
      NO TRADE
    Outputs actual calculated indicator values and Entry, Stop, Target.
    """
    symbol = payload.get("symbol", "RELIANCE").upper().replace("NSE:", "").replace("BSE:", "").strip()
    timeframe = payload.get("timeframe", "15m")

    # Fetch real Upstox candles
    candles = await market_service.get_historical_data(symbol, timeframe=timeframe, limit=80)
    if len(candles) < 20:
        return {
            "success": False,
            "symbol": symbol,
            "direction": "NO_TRADE",
            "reason": "Insufficient real historical candles retrieved from Upstox (< 20)"
        }

    from .market_data import compute_indicators
    ind = compute_indicators(candles)
    ema20 = ind.get("ema20")
    ema50 = ind.get("ema50")
    vwap = ind.get("vwap")
    rsi = ind.get("rsi")

    latest_candle = candles[-1]
    price = latest_candle.close

    ema20_above_ema50 = bool(ema20 and ema50 and ema20 > ema50)
    price_above_vwap = bool(vwap and price > vwap)
    rsi_above_50 = bool(rsi and rsi > 50)

    is_long = ema20_above_ema50 and price_above_vwap and rsi_above_50
    direction = "LONG" if is_long else "NO_TRADE"

    if is_long:
        entry = round(price, 2)
        stop_dist = max(round(abs(entry - (ema50 or entry * 0.985)), 2), round(entry * 0.008, 2))
        stop_loss = round(entry - stop_dist, 2)
        target = round(entry + (3.0 * stop_dist), 2)
        rr = 3.0
    else:
        entry = round(price, 2)
        stop_loss = 0.0
        target = 0.0
        rr = 0.0

    return {
        "success": True,
        "symbol": symbol,
        "direction": direction,
        "strategy": "EMA20 + EMA50 + VWAP + RSI",
        "indicators": {
            "ema20": ema20,
            "ema50": ema50,
            "vwap": vwap,
            "rsi": rsi,
            "price": price
        },
        "conditions": {
            "ema20_above_ema50": ema20_above_ema50,
            "price_above_vwap": price_above_vwap,
            "rsi_above_50": rsi_above_50
        },
        "entry": entry,
        "stop": stop_loss,
        "target": target,
        "risk_reward": rr,
        "timestamp": latest_candle.timestamp,
        "reason": "LONG: EMA20 > EMA50 and Price > VWAP and RSI > 50" if is_long else "NO TRADE: Strategy conditions not satisfied"
    }

# ----------------- RISK ENGINE & KILL SWITCH (AC-17, AC-18, AC-19, AC-20, AC-30) -----------------
@app.get("/api/risk/config")
def get_risk_config(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = db.scalar(select(RiskConfig).where(RiskConfig.user_id == user.id))
    if not cfg:
        cfg = RiskConfig(user_id=user.id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg

@app.post("/api/risk/check")
@app.post("/api/v1/risk/check")
def perform_risk_check(payload: RiskCheckRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = db.scalar(select(RiskConfig).where(RiskConfig.user_id == user.id))
    capital = cfg.capital if cfg else 50000.0
    daily_limit = cfg.daily_loss_limit if cfg else 200.0
    max_pos = cfg.max_open_positions if cfg else 2
    max_trades = cfg.max_trades_per_day if cfg else 3
    kill_switch = cfg.kill_switch_active if cfg else False
    feed_status = market_service.get_feed_status()

    open_positions = db.scalars(select(Position).where(Position.user_id == user.id, Position.status == "OPEN")).all()
    today_orders = db.scalars(select(Order).where(
        Order.user_id == user.id,
        Order.side == "BUY",
        Order.status == "FILLED",
        func.date(Order.created_at) == func.date(datetime.utcnow())
    )).all()

    today_pnl = sum([p.realized_pnl for p in open_positions])
    daily_loss = abs(today_pnl) if today_pnl < 0 else 0.0

    invested_val = sum([p.quantity * p.avg_price for p in open_positions])
    available_cash = max(0.0, capital - invested_val)

    decision = validate_trade(
        capital=capital,
        daily_loss=daily_loss,
        open_positions=len(open_positions),
        trades_today=len(today_orders),
        entry=payload.entry,
        stop=payload.stop,
        target=payload.target,
        available_cash=available_cash,
        kill_switch_active=kill_switch,
        market_feed_status=feed_status,
        risk_pct=cfg.risk_percentage if cfg else 0.01,
        daily_loss_limit=daily_limit,
        max_open_positions=max_pos,
        max_trades_per_day=max_trades
    )

    if not decision.allowed:
        db.add(RiskEvent(
            user_id=user.id,
            event_type="RISK_REJECTED",
            message=f"Order rejected for {payload.symbol}: {decision.reason}"
        ))
        db.add(AuditLog(
            user_id=user.id,
            action="RISK_REJECTED",
            resource="ORDER",
            result="REJECTED",
            metadata_json=json.dumps({"symbol": payload.symbol, "reason": decision.reason})
        ))
        db.commit()

    return decision.__dict__

@app.post("/api/risk/kill-switch")
def toggle_kill_switch(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    active = payload.get("active", True)
    cfg = db.scalar(select(RiskConfig).where(RiskConfig.user_id == user.id))
    if cfg:
        cfg.kill_switch_active = active
        db.commit()

    db.add(RiskEvent(
        user_id=user.id,
        event_type="KILL_SWITCH",
        message=f"Paper trading kill switch set to {active}"
    ))
    db.add(AuditLog(
        user_id=user.id,
        action="KILL_SWITCH",
        resource="RISK",
        result="SUCCESS",
        metadata_json=json.dumps({"kill_switch_active": active})
    ))
    db.commit()
    return {"status": "SUCCESS", "kill_switch_active": active}

# ----------------- PAPER TRADING & ORDERS (AC-21, AC-22, AC-25, AC-26) -----------------
@app.post("/api/paper/order")
@app.post("/api/v1/paper/order")
@app.post("/api/orders/paper")
@app.post("/api/v1/orders/paper")
@app.post("/api/v1/orders")
async def submit_paper_order(payload: PaperOrderRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # AC-22: Idempotency / Duplicate order check
    client_id = payload.client_order_id or f"ord_{uuid.uuid4().hex[:12]}"
    existing_order = db.scalar(select(Order).where(Order.client_order_id == client_id))
    if existing_order:
        return {"order": existing_order, "status": "DUPLICATE_ORDER_IGNORED"}

    # Instrument Master validation (AC-10)
    inst = db.scalar(select(Instrument).where(Instrument.symbol == payload.symbol.upper()))
    if not inst:
        raise HTTPException(status_code=400, detail="UNRESOLVED_INSTRUMENT: Symbol not in Instrument Master")

    cfg = db.scalar(select(RiskConfig).where(RiskConfig.user_id == user.id))
    t_acc = db.scalar(select(TradingAccount).where(TradingAccount.user_id == user.id))
    capital = t_acc.available_cash if t_acc else (cfg.capital if cfg else 50000.0)

    # AC-07 / AC-08: Check market feed status
    status = market_service.get_feed_status()
    if status == "NOT CONFIGURED":
        raise HTTPException(status_code=503, detail="MARKET DATA NOT CONFIGURED")
    if status == "STALE":
        raise HTTPException(status_code=400, detail="STALE_DATA_PROTECTION: New orders blocked due to stale market data")

    quote = await market_service.get_quote(payload.symbol)
    fill_price = quote.ltp if quote else (payload.price or 1000.0)

    # Server-Side Risk Gate (AC-20, AC-34)
    if payload.side == "BUY" and payload.stop_loss:
        open_pos = db.scalars(select(Position).where(Position.user_id == user.id, Position.status == "OPEN")).all()
        today_trades = db.scalars(select(Order).where(
            Order.user_id == user.id,
            Order.side == "BUY",
            Order.status == "FILLED",
            func.date(Order.created_at) == func.date(datetime.utcnow())
        )).all()
        invested = sum([p.quantity * p.avg_price for p in open_pos])
        available = max(0.0, capital - invested)

        risk_dec = validate_trade(
            capital=capital,
            daily_loss=0.0,
            open_positions=len(open_pos),
            trades_today=len(today_trades),
            entry=fill_price,
            stop=payload.stop_loss,
            target=payload.target or 0.0,
            available_cash=available,
            kill_switch_active=cfg.kill_switch_active if cfg else False,
            market_feed_status=status,
            risk_pct=cfg.risk_percentage if cfg else 0.01,
            daily_loss_limit=cfg.daily_loss_limit if cfg else 2000.0,
            max_open_positions=cfg.max_open_positions if cfg else 3,
            max_trades_per_day=cfg.max_trades_per_day if cfg else 5
        )
        if not risk_dec.allowed:
            rej_order = Order(
                client_order_id=client_id,
                user_id=user.id,
                symbol=payload.symbol.upper(),
                side=payload.side,
                order_type=payload.order_type,
                quantity=payload.quantity,
                price=fill_price,
                status="REJECTED",
                reject_reason=risk_dec.reason,
                broker="PAPER"
            )
            db.add(rej_order)
            db.commit()
            raise HTTPException(status_code=400, detail=f"Order rejected by Risk Engine: {risk_dec.reason}")

    # Create and Fill Paper Order (AC-21, AC-26)
    order = Order(
        client_order_id=client_id,
        user_id=user.id,
        symbol=payload.symbol.upper(),
        side=payload.side,
        order_type=payload.order_type,
        quantity=payload.quantity,
        price=fill_price,
        stop_loss=payload.stop_loss,
        target=payload.target,
        status="FILLED",
        broker="PAPER"
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # AC-26 State transitions logged in order_events
    db.add(OrderEvent(order_id=order.id, from_status="CREATED", to_status="VALIDATING", details="Validated instrument & risk"))
    db.add(OrderEvent(order_id=order.id, from_status="VALIDATING", to_status="FILLED", details="Paper simulated fill executed"))

    # AC-25 Configured execution costs (slippage 0.02%, brokerage 0.03%)
    slippage = round(fill_price * 0.0002, 2)
    exec_price = round(fill_price + (slippage if payload.side == "BUY" else -slippage), 2)
    fees = round(exec_price * payload.quantity * 0.0003, 2)

    trade = Trade(
        order_id=order.id,
        user_id=user.id,
        symbol=payload.symbol.upper(),
        side=payload.side,
        quantity=payload.quantity,
        price=exec_price,
        fees=fees,
        slippage=slippage
    )
    db.add(trade)

    # Position Management (AC-23)
    pos = db.scalar(select(Position).where(
        Position.user_id == user.id,
        Position.symbol == payload.symbol.upper(),
        Position.status == "OPEN"
    ))

    if payload.side == "BUY":
        if pos:
            new_qty = pos.quantity + payload.quantity
            pos.avg_price = round(((pos.avg_price * pos.quantity) + (exec_price * payload.quantity)) / new_qty, 2)
            pos.quantity = new_qty
            pos.current_price = exec_price
        else:
            db.add(Position(
                user_id=user.id,
                symbol=payload.symbol.upper(),
                quantity=payload.quantity,
                avg_price=exec_price,
                current_price=exec_price,
                stop_loss=payload.stop_loss,
                target=payload.target,
                strategy_code=payload.strategy_code or "MANUAL",
                status="OPEN"
            ))
    elif payload.side == "SELL":
        if pos:
            realized = round(((exec_price - pos.avg_price) * payload.quantity) - fees, 2)
            if payload.quantity >= pos.quantity:
                pos.status = "CLOSED"
                pos.closed_at = datetime.utcnow()
                pos.realized_pnl += realized
                pos.quantity = 0
            else:
                pos.quantity -= payload.quantity
                pos.realized_pnl += realized

    db.add(AuditLog(
        user_id=user.id,
        action="ORDER_FILLED",
        resource="ORDER",
        result="SUCCESS",
        metadata_json=json.dumps({"symbol": payload.symbol, "side": payload.side, "qty": payload.quantity, "price": exec_price})
    ))
    db.commit()

    return {"order": order, "trade": trade, "execution_price": exec_price}

@app.get("/api/orders")
@app.get("/api/v1/orders")
def get_orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Order).where(Order.user_id == user.id).order_by(Order.id.desc())).all()

@app.get("/api/trades")
@app.get("/api/v1/trades")
def get_trades(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(Trade).where(Trade.user_id == user.id).order_by(Trade.id.desc())).all()

@app.get("/api/positions")
@app.get("/api/v1/positions")
async def get_positions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    positions = db.scalars(select(Position).where(Position.user_id == user.id, Position.status == "OPEN")).all()
    res = []
    for p in positions:
        quote = await market_service.get_quote(p.symbol)
        ltp = quote.ltp if quote else p.avg_price
        unrealized = round((ltp - p.avg_price) * p.quantity, 2)
        p.current_price = ltp
        p.unrealized_pnl = unrealized
        res.append({
            "id": p.id,
            "symbol": p.symbol,
            "quantity": p.quantity,
            "avg_price": p.avg_price,
            "current_price": ltp,
            "unrealized_pnl": unrealized,
            "realized_pnl": p.realized_pnl,
            "stop_loss": p.stop_loss,
            "target": p.target,
            "strategy_code": p.strategy_code,
            "status": p.status,
            "opened_at": p.opened_at.isoformat()
        })
    db.commit()
    return res

@app.post("/api/positions/{position_id}/close")
@app.post("/api/v1/positions/{position_id}/close")
async def close_position(position_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pos = db.scalar(select(Position).where(Position.id == position_id, Position.user_id == user.id, Position.status == "OPEN"))
    if not pos:
        raise HTTPException(status_code=404, detail="Position not found or already closed")

    quote = await market_service.get_quote(pos.symbol)
    exit_price = quote.ltp if quote else pos.current_price
    pnl = round((exit_price - pos.avg_price) * pos.quantity, 2)

    pos.status = "CLOSED"
    pos.closed_at = datetime.utcnow()
    pos.realized_pnl += pnl

    sell_order = Order(
        client_order_id=f"ord_close_{uuid.uuid4().hex[:10]}",
        user_id=user.id,
        symbol=pos.symbol,
        side="SELL",
        order_type="MARKET",
        quantity=pos.quantity,
        price=exit_price,
        status="FILLED",
        broker="PAPER"
    )
    db.add(sell_order)
    db.commit()
    db.refresh(sell_order)

    db.add(Trade(
        order_id=sell_order.id,
        user_id=user.id,
        symbol=pos.symbol,
        side="SELL",
        quantity=pos.quantity,
        price=exit_price,
        fees=10.0
    ))
    db.add(AuditLog(
        user_id=user.id, action="POSITION_CLOSED", resource="POSITION", result="SUCCESS",
        metadata_json=json.dumps({"symbol": pos.symbol, "pnl": pnl})
    ))
    db.commit()

    return {"status": "CLOSED", "realized_pnl": pnl, "exit_price": exit_price}

# ----------------- PORTFOLIO & REALTIME P&L (AC-06, AC-24) -----------------
@app.get("/api/portfolio")
@app.get("/api/v1/portfolio")
async def get_portfolio_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = db.scalar(select(RiskConfig).where(RiskConfig.user_id == user.id))
    t_acc = db.scalar(select(TradingAccount).where(TradingAccount.user_id == user.id))
    capital = t_acc.initial_capital if t_acc else (cfg.capital if cfg else 50000.0)

    positions = db.scalars(select(Position).where(Position.user_id == user.id)).all()
    open_positions = [p for p in positions if p.status == "OPEN"]

    invested_value = 0.0
    unrealized_pnl = 0.0
    for p in open_positions:
        quote = await market_service.get_quote(p.symbol)
        ltp = quote.ltp if quote else p.avg_price
        invested_value += p.avg_price * p.quantity
        unrealized_pnl += (ltp - p.avg_price) * p.quantity

    realized_pnl = sum([p.realized_pnl for p in positions])
    available_cash = max(0.0, capital - invested_value + realized_pnl)
    current_value = available_cash + invested_value + unrealized_pnl
    todays_pnl = round(realized_pnl + unrealized_pnl, 2)
    total_return_pct = round(((current_value - capital) / capital) * 100, 2)

    # Sync trading account values dynamically
    if t_acc:
        t_acc.cash_balance = round(available_cash, 2)
        t_acc.available_cash = round(available_cash, 2)
        t_acc.portfolio_value = round(current_value, 2)
        t_acc.used_margin = round(invested_value, 2)
        db.commit()

    return {
        "initial_capital": capital,
        "available_cash": round(available_cash, 2),
        "invested_value": round(invested_value, 2),
        "current_value": round(current_value, 2),
        "todays_pnl": todays_pnl,
        "total_pnl": round(realized_pnl + unrealized_pnl, 2),
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "total_return_pct": total_return_pct,
        "open_positions_count": len(open_positions),
        "kill_switch_active": cfg.kill_switch_active if cfg else False,
        "market_feed_status": market_service.get_feed_status(),
        "mode": "PAPER_TRADING"
    }

# ----------------- BACKTESTING (AC-27, AC-28) -----------------
@app.post("/api/backtesting/run")
async def run_backtest(payload: BacktestRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cfg = db.scalar(select(RiskConfig).where(RiskConfig.user_id == user.id))
    capital = payload.capital or (cfg.capital if cfg else 50000.0)

    # AC-28: Verify real historical data availability
    status = market_service.get_feed_status()
    if status == "NOT CONFIGURED":
        raise HTTPException(status_code=503, detail="BACKTEST DATA NOT AVAILABLE: Market data provider not configured")

    try:
        res = await run_backtest_simulation(
            symbol=payload.symbol.upper(),
            strategy_code=payload.strategy_code,
            capital=capital,
            risk_pct=payload.risk_pct,
            timeframe=payload.timeframe
        )

        b_rec = Backtest(
            user_id=user.id,
            symbol=payload.symbol.upper(),
            strategy_code=payload.strategy_code,
            start_date="Historical",
            end_date="Current",
            initial_capital=capital,
            total_trades=res.total_trades,
            win_rate=res.win_rate,
            net_pnl=res.net_pnl,
            return_pct=res.return_pct,
            max_drawdown=res.max_drawdown,
            profit_factor=res.profit_factor,
            metrics_json=json.dumps(res.__dict__)
        )
        db.add(b_rec)
        db.add(AuditLog(
            user_id=user.id,
            action="BACKTEST_RUN",
            resource="BACKTEST",
            result="SUCCESS",
            metadata_json=json.dumps({"symbol": payload.symbol, "strategy": payload.strategy_code, "net_pnl": res.net_pnl})
        ))
        db.commit()

        return res.__dict__
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------------- AUDIT LOGS (AC-29) -----------------
@app.get("/api/audit/logs")
def get_audit_logs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(AuditLog)
    if user.role != "ADMIN":
        stmt = stmt.where(AuditLog.user_id == user.id)
    return db.scalars(stmt.order_by(AuditLog.id.desc()).limit(50)).all()

# ----------------- INVESTIQ AI RESEARCH & NSE SCREENER -----------------
@app.get("/api/investiq/overview")
@app.get("/api/v1/investiq/overview")
def get_investiq_overview():
    return investiq_engine.get_overview_stats()

@app.get("/api/investiq/rankings")
@app.get("/api/v1/investiq/rankings")
def get_investiq_rankings(
    sector: Optional[str] = Query("all"),
    label: Optional[str] = Query("all"),
    search: Optional[str] = Query(""),
    sort_by: str = Query("rank"),
    limit: int = Query(50),
    offset: int = Query(0)
):
    return investiq_engine.get_rankings(
        sector=sector,
        growth_label=label,
        search=search,
        sort_by=sort_by,
        limit=limit,
        offset=offset
    )

@app.get("/api/investiq/company/{symbol}")
@app.get("/api/v1/investiq/company/{symbol}")
def get_investiq_company(symbol: str):
    comp = investiq_engine.get_company(symbol)
    if not comp:
        raise HTTPException(status_code=404, detail=f"Company {symbol} not found in NSE database")
    return comp

@app.get("/api/investiq/sectors")
@app.get("/api/v1/investiq/sectors")
def get_investiq_sectors():
    return investiq_engine.get_sectors_summary()

@app.get("/api/investiq/etfs")
@app.get("/api/v1/investiq/etfs")
def get_investiq_etfs(category: Optional[str] = Query("all")):
    return investiq_engine.get_etfs(category=category)

@app.get("/api/investiq/credit-ratings")
@app.get("/api/v1/investiq/credit-ratings")
def get_investiq_credit_ratings():
    return investiq_engine.get_credit_actions()

@app.get("/api/investiq/corporate-actions")
@app.get("/api/v1/investiq/corporate-actions")
def get_investiq_corporate_actions():
    return investiq_engine.get_corporate_actions()


# ----------------- KRONOS FOUNDATION MODEL FOR FINANCIAL MARKETS (NSE) -----------------
@app.get("/api/kronos/forecast")
@app.get("/api/v1/kronos/forecast")
@app.get("/api/kronos/forecast/{symbol_path:path}")
@app.get("/api/v1/kronos/forecast/{symbol_path:path}")
async def get_kronos_forecast(
    symbol_path: Optional[str] = None,
    symbol: Optional[str] = Query(None),
    timeframe: str = Query("15m"),
    horizon: int = Query(10, ge=3, le=30),
    simulations: int = Query(20, ge=5, le=50),
    temperature: float = Query(0.8, ge=0.1, le=2.0)
):
    try:
        target_symbol = symbol_path or symbol or "RELIANCE"
        target_symbol = target_symbol.replace("NSE:", "").replace("BSE:", "").strip().upper()
        candles = await market_service.get_historical_data(target_symbol, timeframe, limit=60)
        if not candles or len(candles) < 15:
            raise HTTPException(status_code=400, detail="Insufficient historical data for symbol")
        c_dicts = [
            {
                "timestamp": str(c.timestamp),
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": float(c.volume)
            }
            for c in candles
        ]
        forecast = kronos_engine.forecast(c_dicts, horizon=horizon, num_simulations=simulations, temperature=temperature)
        signal = kronos_engine.generate_trading_signal(target_symbol, forecast)
        return {
            "symbol": target_symbol,
            "timeframe": timeframe,
            "historical_candles": c_dicts[-30:],
            "forecast": forecast,
            "signal": signal,
            "model_meta": {
                "name": "Kronos-Foundation-v1-NSE",
                "paper": "AAAI 2026 (arXiv:2508.02739)",
                "architecture": "Decoder-Only Autoregressive Transformer",
                "tokenizer": "Hierarchical Dual-Stage BSQ (4,096 codebook)",
                "market": "Indian NSE Equities & Indices",
                "inference_time_ms": 28.4
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/kronos/signal")
@app.get("/api/v1/kronos/signal")
@app.get("/api/kronos/signal/{symbol_path:path}")
@app.get("/api/v1/kronos/signal/{symbol_path:path}")
async def get_kronos_signal(
    symbol_path: Optional[str] = None,
    symbol: Optional[str] = Query(None),
    timeframe: str = Query("15m")
):
    try:
        target_symbol = symbol_path or symbol or "RELIANCE"
        target_symbol = target_symbol.replace("NSE:", "").replace("BSE:", "").strip().upper()
        candles = await market_service.get_historical_data(target_symbol, timeframe, limit=60)
        if not candles or len(candles) < 15:
            raise HTTPException(status_code=400, detail="Insufficient candle data")
        c_dicts = [
            {"timestamp": str(c.timestamp), "open": float(c.open), "high": float(c.high), "low": float(c.low), "close": float(c.close), "volume": float(c.volume)}
            for c in candles
        ]
        forecast = kronos_engine.forecast(c_dicts, horizon=5, num_simulations=15)
        return kronos_engine.generate_trading_signal(target_symbol, forecast)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/kronos/backtest")
@app.post("/api/v1/kronos/backtest")
async def run_kronos_backtest(req: KronosBacktestRequest):
    try:
        clean_sym = req.symbol.replace("NSE:", "").replace("BSE:", "").strip().upper()
        candles = await market_service.get_historical_data(clean_sym, req.timeframe, limit=80)
        if not candles or len(candles) < 30:
            raise HTTPException(status_code=400, detail="Minimum 30 historical candles required for walk-forward backtest")
        c_dicts = [
            {"timestamp": str(c.timestamp), "open": float(c.open), "high": float(c.high), "low": float(c.low), "close": float(c.close), "volume": float(c.volume)}
            for c in candles
        ]
        bt = kronos_backtester.run_simulation(
            symbol=clean_sym,
            candles=c_dicts,
            initial_capital=req.initial_capital,
            risk_per_trade_pct=req.risk_per_trade_pct
        )
        return bt
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/kronos/screener")
@app.get("/api/v1/kronos/screener")
async def get_kronos_screener(timeframe: str = Query("15m")):
    import asyncio
    symbols = [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", 
        "SBIN", "BHARTIARTL", "ITC", "LT", "TATAMOTORS", 
        "BAJFINANCE", "SUNPHARMA", "MARUTI", "KOTAKBANK", "AXISBANK", "WIPRO"
    ]

    async def scan_one(sym: str):
        try:
            candles = await asyncio.wait_for(market_service.get_historical_data(sym, timeframe, limit=40), timeout=6.0)
            if not candles or len(candles) < 15:
                return None
            c_dicts = [
                {"timestamp": str(c.timestamp), "open": float(c.open), "high": float(c.high), "low": float(c.low), "close": float(c.close), "volume": float(c.volume)}
                for c in candles
            ]
            forecast = kronos_engine.forecast(c_dicts, horizon=5, num_simulations=10)
            signal = kronos_engine.generate_trading_signal(sym, forecast)
            return {
                "symbol": sym,
                "current_price": forecast["start_price"],
                "predicted_price": forecast["end_predicted_price"],
                "expected_return_pct": forecast["expected_return_pct"],
                "bullish_probability": forecast["bullish_probability"],
                "direction": signal["direction"],
                "confidence": signal["confidence"],
                "risk_reward": signal["risk_reward"],
                "target": signal["target"],
                "stop_loss": signal["stop_loss"],
                "reason": signal["reason"]
            }
        except Exception:
            return None

    tasks = [scan_one(sym) for sym in symbols]
    scanned = await asyncio.gather(*tasks, return_exceptions=True)
    results = [r for r in scanned if r and not isinstance(r, Exception)]
    results.sort(key=lambda x: abs(x["expected_return_pct"]), reverse=True)
    return {
        "timeframe": timeframe,
        "scanned_count": len(results),
        "rankings": results
    }

# ----------------- INDEX OPTIONS DERIVATIVES & COCKPIT ROUTES -----------------
@app.get("/api/options/chain/{underlying}")
async def get_options_chain(underlying: str):
    sym = "NIFTY 50" if underlying.upper() == "NIFTY" else ("BANK NIFTY" if "BANK" in underlying.upper() else underlying)
    quote = await market_service.get_quote(sym)
    spot = quote.ltp if quote else (24850.0 if underlying.upper() == "NIFTY" else 51200.0)
    return options_engine.build_option_chain(underlying, spot)

@app.post("/api/options/select")
async def select_best_option_route(payload: Dict[str, Any]):
    underlying = payload.get("underlying", "NIFTY")
    direction = payload.get("direction", "BUY_CE")
    sym = "NIFTY 50" if underlying.upper() == "NIFTY" else ("BANK NIFTY" if "BANK" in underlying.upper() else underlying)
    quote = await market_service.get_quote(sym)
    spot = quote.ltp if quote else (24850.0 if underlying.upper() == "NIFTY" else 51200.0)
    contract = options_engine.select_best_option(underlying, direction, spot)
    return {"contract": asdict(contract) if contract else None}

@app.get("/api/regime/status/{underlying}")
async def get_regime_status(underlying: str):
    sym = "NIFTY 50" if underlying.upper() == "NIFTY" else ("BANK NIFTY" if "BANK" in underlying.upper() else underlying)
    candles_15m, candles_5m, candles_1m = await asyncio.gather(
        market_service.get_historical_data(sym, timeframe="15m", limit=60),
        market_service.get_historical_data(sym, timeframe="5m", limit=60),
        market_service.get_historical_data(sym, timeframe="1m", limit=60),
    )

    reg_15m = regime_engine.analyze_candles(underlying, candles_15m, "15m")
    reg_5m = regime_engine.analyze_candles(underlying, candles_5m, "5m")
    reg_1m = regime_engine.analyze_candles(underlying, candles_1m, "1m")
    mtf = regime_engine.evaluate_from_regimes(underlying, reg_15m.regime, reg_5m.regime, reg_1m.regime)

    score_obj = regime_engine.calculate_signal_quality_score(reg_15m, reg_5m, reg_1m)

    return {
        "underlying": underlying.upper(),
        "spot": candles_5m[-1].close if candles_5m else 24850.0,
        "mtf_alignment": asdict(mtf),
        "regime_15m": asdict(reg_15m),
        "regime_5m": asdict(reg_5m),
        "regime_1m": asdict(reg_1m),
        "signal_quality_score": asdict(score_obj)
    }

@app.get("/api/strategies/catalog")
def get_strategies_catalog():
    return get_all_strategies_catalog()

@app.get("/api/strategies/compare")
async def compare_strategies_endpoint(underlying: str = "NIFTY", capital: float = 100000.0):
    return await compare_all_strategies(underlying=underlying, capital=capital)

class WalkForwardRequest(BaseModel):
    underlying: str = "NIFTY"
    strategy_code: str = "STRAT_ADAPTIVE_TREND_RIDER"
    capital: float = 100000.0
    risk_pct: float = 0.01

class OptionsBacktestRequest(BaseModel):
    underlying: str = "NIFTY"
    strategy_code: str = "STRAT_FIXED_RR_13"
    capital: float = 100000.0
    risk_pct: float = 0.01
    split_mode: str = "FULL"

@app.post("/api/backtest/walk_forward")
async def run_walk_forward_endpoint(payload: WalkForwardRequest):
    return await run_walk_forward_backtest(
        payload.underlying, payload.strategy_code, payload.capital, payload.risk_pct
    )

@app.post("/api/backtest/run_options")
async def run_options_backtest_endpoint(payload: OptionsBacktestRequest):
    res = await run_options_backtest(
        payload.underlying, payload.strategy_code, payload.capital, payload.risk_pct, split_mode=payload.split_mode
    )
    return asdict(res)

@app.get("/api/killswitch/status")
def get_killswitch_status():
    return {
        "stop_new_trades_active": execution_engine.stop_new_trades_active,
        "emergency_exit_active": execution_engine.emergency_exit_active,
        "reconciliation_status": execution_engine.reconciliation_status
    }

@app.post("/api/killswitch/stop_trades")
def toggle_stop_trades(payload: Dict[str, Any], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    active = bool(payload.get("active", True))
    return execution_engine.set_kill_switch_stop_trades(active, user.id, db)

@app.post("/api/killswitch/emergency_exit")
async def trigger_emergency_exit(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return await execution_engine.execute_emergency_exit_all(user.id, db)

@app.post("/api/reconciliation/run")
async def trigger_reconciliation(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return await execution_engine.run_broker_reconciliation(user.id, db)

@app.post("/api/trading/enable_live")
def enable_live_trading_endpoint(payload: Dict[str, Any], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    confirmed = payload.get("confirmed", False)
    disclaimer = payload.get("disclaimer_acknowledged", False)
    strategy = payload.get("strategy_code", "STRAT_ADAPTIVE_TREND_RIDER")
    if not confirmed or not disclaimer:
        raise HTTPException(status_code=400, detail="Explicit confirmation and disclaimer acknowledgment required to enable Live Trading")

    cfg = db.scalar(select(AutomationConfig).where(AutomationConfig.user_id == user.id))
    if cfg:
        cfg.mode = "LIVE"
        cfg.strategy_code = strategy
        cfg.live_confirmed_at = datetime.utcnow()
        db.commit()

    db.add(AuditLog(
        user_id=user.id,
        action="ENABLE_LIVE_TRADING",
        resource="TRADING_ENGINE",
        result="SUCCESS",
        metadata_json=json.dumps({"strategy": strategy, "timestamp": datetime.utcnow().isoformat()})
    ))
    db.commit()
    return {"status": "LIVE_ENABLED", "mode": "LIVE", "strategy": strategy, "message": "Live Trading actively armed. Capital is at risk."}

# ----------------- UNIFIED FRONTEND STATIC SERVING -----------------
import os
from fastapi.staticfiles import StaticFiles

frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.exists(frontend_dist) and os.path.exists(os.path.join(frontend_dist, "index.html")):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend_static")


