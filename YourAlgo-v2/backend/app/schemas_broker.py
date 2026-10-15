from typing import Optional
from pydantic import BaseModel

class BrokerConnectionRequest(BaseModel):
    broker_name: str = "UPSTOX" # UPSTOX only
    client_id: Optional[str] = ""
    access_token: str
    feed_mode: Optional[str] = "LIVE_MARKET_DATA" # "LIVE_MARKET_DATA" (Safe default)
