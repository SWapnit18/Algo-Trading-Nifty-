from datetime import datetime
from sqlalchemy import String, Float, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="USER") # USER or ADMIN
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Instrument(Base):
    __tablename__ = "instruments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    tradingsymbol: Mapped[str] = mapped_column(String(80))
    exchange: Mapped[str] = mapped_column(String(20), default="NSE")
    segment: Mapped[str] = mapped_column(String(20), default="EQUITY")
    security_id: Mapped[str] = mapped_column(String(50))
    isin: Mapped[str] = mapped_column(String(50), default="")
    instrument_type: Mapped[str] = mapped_column(String(20), default="EQUITY")
    tick_size: Mapped[float] = mapped_column(Float, default=0.05)
    lot_size: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Watchlist(Base):
    __tablename__ = "watchlists"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    watchlist_id: Mapped[int] = mapped_column(Integer, ForeignKey("watchlists.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(80), index=True)
    instrument_id: Mapped[int] = mapped_column(Integer, nullable=True)

class Strategy(Base):
    __tablename__ = "strategies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(80), unique=True) # STRAT_EMA_VWAP, STRAT_ORB, STRAT_VWAP_PULLBACK
    description: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(30), default="PAPER")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    config_json: Mapped[str] = mapped_column(Text, default="{}")

class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(80), index=True)
    strategy_code: Mapped[str] = mapped_column(String(80))
    direction: Mapped[str] = mapped_column(String(10)) # BUY, SELL, NO_TRADE
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    target: Mapped[float] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer)
    risk_amount: Mapped[float] = mapped_column(Float)
    risk_reward: Mapped[float] = mapped_column(Float, default=3.0)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_order_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1)
    symbol: Mapped[str] = mapped_column(String(80), index=True)
    side: Mapped[str] = mapped_column(String(10)) # BUY, SELL
    order_type: Mapped[str] = mapped_column(String(20), default="MARKET")
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    target: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="CREATED") # CREATED, VALIDATING, OPEN, FILLED, REJECTED, CANCELLED, CLOSED
    reject_reason: Mapped[str] = mapped_column(Text, default="")
    broker: Mapped[str] = mapped_column(String(30), default="PAPER")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OrderEvent(Base):
    __tablename__ = "order_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), index=True)
    from_status: Mapped[str] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1)
    symbol: Mapped[str] = mapped_column(String(80), index=True)
    side: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    slippage: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Position(Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1)
    symbol: Mapped[str] = mapped_column(String(80), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    avg_price: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float] = mapped_column(Float)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    target: Mapped[float | None] = mapped_column(Float, nullable=True)
    strategy_code: Mapped[str] = mapped_column(String(80), default="MANUAL")
    status: Mapped[str] = mapped_column(String(20), default="OPEN") # OPEN, CLOSED
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1)
    capital: Mapped[float] = mapped_column(Float)
    available_cash: Mapped[float] = mapped_column(Float)
    invested_value: Mapped[float] = mapped_column(Float)
    current_value: Mapped[float] = mapped_column(Float)
    todays_pnl: Mapped[float] = mapped_column(Float)
    total_pnl: Mapped[float] = mapped_column(Float)
    total_return_pct: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class RiskConfig(Base):
    __tablename__ = "risk_configs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, default=1)
    capital: Mapped[float] = mapped_column(Float, default=10000.0)
    risk_percentage: Mapped[float] = mapped_column(Float, default=0.01) # 1%
    daily_loss_limit: Mapped[float] = mapped_column(Float, default=200.0)
    max_open_positions: Mapped[int] = mapped_column(Integer, default=2)
    max_trades_per_day: Mapped[int] = mapped_column(Integer, default=3)
    risk_reward: Mapped[float] = mapped_column(Float, default=3.0)
    kill_switch_active: Mapped[bool] = mapped_column(Boolean, default=False)

class RiskEvent(Base):
    __tablename__ = "risk_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1)
    event_type: Mapped[str] = mapped_column(String(80)) # RISK_REJECTED, KILL_SWITCH, DAILY_LIMIT_EXCEEDED
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1)
    action: Mapped[str] = mapped_column(String(100))
    resource: Mapped[str] = mapped_column(String(100))
    result: Mapped[str] = mapped_column(String(50)) # SUCCESS, REJECTED, ERROR
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Backtest(Base):
    __tablename__ = "backtests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1)
    symbol: Mapped[str] = mapped_column(String(80))
    strategy_code: Mapped[str] = mapped_column(String(80))
    start_date: Mapped[str] = mapped_column(String(30))
    end_date: Mapped[str] = mapped_column(String(30))
    initial_capital: Mapped[float] = mapped_column(Float, default=10000.0)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    net_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, default=0.0)
    profit_factor: Mapped[float] = mapped_column(Float, default=0.0)
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class BrokerConnection(Base):
    __tablename__ = "broker_connections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    broker_name: Mapped[str] = mapped_column(String(50), default="UPSTOX") # UPSTOX
    client_id: Mapped[str] = mapped_column(String(100), default="")
    encrypted_token: Mapped[str] = mapped_column(Text, default="")
    api_key: Mapped[str] = mapped_column(String(200), default="")
    is_connected: Mapped[bool] = mapped_column(Boolean, default=True)
    trading_permission: Mapped[str] = mapped_column(String(20), default="PAPER") # PAPER, LIVE, DISABLED
    feed_status: Mapped[str] = mapped_column(String(20), default="LIVE")
    available_cash: Mapped[float] = mapped_column(Float, default=50000.0)
    connected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_sync_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class AutomationConfig(Base):
    __tablename__ = "automation_configs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, default=1)
    mode: Mapped[str] = mapped_column(String(20), default="PAPER") # PAPER, LIVE, DISABLED
    is_running: Mapped[bool] = mapped_column(Boolean, default=False)
    broker_name: Mapped[str] = mapped_column(String(50), default="UPSTOX") # UPSTOX or PAPER
    strategy_code: Mapped[str] = mapped_column(String(80), default="STRAT_EMA_VWAP")
    risk_per_trade_pct: Mapped[float] = mapped_column(Float, default=0.01) # 1%
    daily_loss_limit: Mapped[float] = mapped_column(Float, default=2000.0)
    max_open_positions: Mapped[int] = mapped_column(Integer, default=3)
    max_trades_per_day: Mapped[int] = mapped_column(Integer, default=5)
    default_risk_reward: Mapped[float] = mapped_column(Float, default=3.0)
    auto_stop_loss: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_target: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_strategy_exit: Mapped[bool] = mapped_column(Boolean, default=True)
    trading_schedule_start: Mapped[str] = mapped_column(String(10), default="09:15")
    trading_schedule_end: Mapped[str] = mapped_column(String(10), default="15:30")
    live_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class AutomationLog(Base):
    __tablename__ = "automation_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    event_type: Mapped[str] = mapped_column(String(50)) # MARKET_DATA, STRATEGY_EVAL, SIGNAL, RISK_CHECK, ORDER_SENT, ORDER_FILLED, STOP_LOSS, TARGET, EXIT, RECONCILIATION
    symbol: Mapped[str] = mapped_column(String(80), default="")
    broker: Mapped[str] = mapped_column(String(50), default="PAPER")
    message: Mapped[str] = mapped_column(Text)
    details_json: Mapped[str] = mapped_column(Text, default="{}")

class ReconciliationRecord(Base):
    __tablename__ = "reconciliation_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, default=1)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    broker: Mapped[str] = mapped_column(String(50), default="UPSTOX")
    status: Mapped[str] = mapped_column(String(30)) # IN_SYNC, MISMATCH_DETECTED
    mismatch_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    details: Mapped[str] = mapped_column(Text, default="{}")

class TradingAccount(Base):
    __tablename__ = "trading_accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    broker: Mapped[str] = mapped_column(String(50), default="UPSTOX")
    account_id: Mapped[str] = mapped_column(String(100), default="")
    account_name: Mapped[str] = mapped_column(String(100), default="Upstox Primary")
    account_type: Mapped[str] = mapped_column(String(50), default="EQUITY") # EQUITY, PAPER
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    initial_capital: Mapped[float] = mapped_column(Float, default=100000.0)
    cash_balance: Mapped[float] = mapped_column(Float, default=100000.0)
    available_cash: Mapped[float] = mapped_column(Float, default=100000.0)
    used_margin: Mapped[float] = mapped_column(Float, default=0.0)
    portfolio_value: Mapped[float] = mapped_column(Float, default=100000.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# ----------------- NSE DATA WAREHOUSE MODELS -----------------
class NSEEquity(Base):
    __tablename__ = "nse_equities"
    symbol: Mapped[str] = mapped_column(String(30), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255))
    series: Mapped[str] = mapped_column(String(10), default="EQ")
    date_of_listing: Mapped[str] = mapped_column(String(30), nullable=True)
    paid_up_value: Mapped[float] = mapped_column(Float, default=0.0)
    market_lot: Mapped[int] = mapped_column(Integer, default=1)
    isin: Mapped[str] = mapped_column(String(30), index=True, default="")
    face_value: Mapped[float] = mapped_column(Float, default=10.0)
    sector: Mapped[str] = mapped_column(String(100), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class NSEEtf(Base):
    __tablename__ = "nse_etfs"
    symbol: Mapped[str] = mapped_column(String(30), primary_key=True)
    security_name: Mapped[str] = mapped_column(String(255))
    underlying_asset: Mapped[str] = mapped_column(String(255), nullable=True)
    category: Mapped[str] = mapped_column(String(100), default="EQUITY")
    isin: Mapped[str] = mapped_column(String(30), index=True, default="")
    listing_date: Mapped[str] = mapped_column(String(30), nullable=True)
    face_value: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class NSESme(Base):
    __tablename__ = "nse_sme_equities"
    symbol: Mapped[str] = mapped_column(String(30), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255))
    series: Mapped[str] = mapped_column(String(10), default="SM")
    listing_date: Mapped[str] = mapped_column(String(30), nullable=True)
    paid_up_value: Mapped[float] = mapped_column(Float, default=0.0)
    market_lot: Mapped[int] = mapped_column(Integer, default=1)
    isin: Mapped[str] = mapped_column(String(30), index=True, default="")
    face_value: Mapped[float] = mapped_column(Float, default=10.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class NSECorporateAction(Base):
    __tablename__ = "nse_corporate_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(255))
    purpose: Mapped[str] = mapped_column(Text)
    record_date: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    bc_start_date: Mapped[str] = mapped_column(String(50), nullable=True)
    bc_end_date: Mapped[str] = mapped_column(String(50), nullable=True)
    payment_date: Mapped[str] = mapped_column(String(50), nullable=True)
    isin: Mapped[str] = mapped_column(String(30), index=True, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class NSECreditRating(Base):
    __tablename__ = "nse_credit_ratings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(30), nullable=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    agency: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    credit_rating: Mapped[str] = mapped_column(String(50), nullable=True)
    rating_action: Mapped[str] = mapped_column(String(100), default="Reaffirm")
    outlook: Mapped[str] = mapped_column(String(50), default="Stable")
    reporting_date: Mapped[str] = mapped_column(String(50), nullable=True)
    date_of_rating: Mapped[str] = mapped_column(String(50), nullable=True)
    isin: Mapped[str] = mapped_column(String(30), index=True, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

