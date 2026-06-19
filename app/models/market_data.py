from pydantic import BaseModel
from datetime import datetime

class MarketDataBase(BaseModel):
    coingecko_id: str
    current_price: float
    high_24h: float | None = None
    low_24h: float | None = None
    total_volume: float | None = None
    market_cap: float | None = None
    price_change_24h: float | None = None
    recorded_at: datetime

class MarketDataDB(MarketDataBase):
    pass

class MarketDataResponse(MarketDataDB):
    pass