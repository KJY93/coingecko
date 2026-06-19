from pydantic import BaseModel

class CoinBase(BaseModel):
    coingecko_id: str
    name: str
    symbol: str

class CoinDB(CoinBase):
    pass

class CoinResponse(CoinBase):
    pass