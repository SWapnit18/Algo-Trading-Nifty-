from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    app_env: str = "development"
    live_trading_enabled: bool = False
    secret_key: str = "youralgo-super-secret-jwt-key-2026-v2-authoritative"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"

    # Upstox Official API v2 Configuration (Single MVP Broker)
    upstox_client_id: str = ""
    upstox_client_secret: str = ""
    upstox_api_key: str = ""
    upstox_api_secret: str = ""
    upstox_redirect_uri: str = "http://localhost:8000/api/v1/brokers/upstox/callback"
    upstox_access_token: str = ""
    upstox_analytics_token: str = ""
    upstox_sandbox_mode: bool = True

    # Market Data & Engine
    market_data_provider: str = "upstox"
    market_data_required: bool = True
    stale_data_seconds: int = 5
    trading_mode: str = "paper"

    # Dynamic Risk Parameters (Defaults, dynamically overridden per account)
    risk_per_trade: float = 0.01
    daily_loss_limit: float = 2000.0
    max_open_positions: int = 3
    max_trades_per_day: int = 5
    default_risk_reward: float = 3.0

    @property
    def effective_db_url(self) -> str:
        url = self.database_url or os.environ.get("DATABASE_URL", "")
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not url:
            return f"sqlite:///{os.path.join(backend_dir, 'youralgo_v2.db')}"
        if url.startswith("sqlite:///./"):
            rel_name = url.replace("sqlite:///./", "")
            return f"sqlite:///{os.path.join(backend_dir, rel_name)}"
        return url

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
