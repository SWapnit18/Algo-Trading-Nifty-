from pydantic import BaseModel
from typing import Optional

class DynamicCapitalUpdate(BaseModel):
    capital: float

class MarketDataConfig(BaseModel):
    provider: str # e.g. "NSE_LIVE", "UPSTOX_LIVE", "NOT_CONFIGURED"
    api_key: Optional[str] = ""
    status: str = "CONFIGURED" # CONFIGURED, NOT_CONFIGURED, STALE, DISCONNECTED

class ScreenerRuleRequest(BaseModel):
    min_rsi: Optional[float] = 50.0
    ema_bullish: Optional[bool] = True
    min_rvol: Optional[float] = 1.0

class WatchlistCreateRequest(BaseModel):
    name: str

class WatchlistRenameRequest(BaseModel):
    name: str
