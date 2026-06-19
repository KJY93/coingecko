from fastapi import APIRouter, HTTPException, Query, Request
from app.core.rate_limiter import limiter
from app.services.repositories.coin import get_all_coins
from app.services.repositories.market_data import get_latest_market_data, get_market_data_history
from app.services.cache import get_cached, set_cached, delete_cached
from datetime import datetime
from app.models.coin import CoinResponse
from app.models.market_data import MarketDataResponse

router = APIRouter(prefix="/coins", tags=["coins"])

@router.get("/", response_model=list[CoinResponse])
@limiter.limit("30/minute")
async def list_coins(request: Request, limit: int = Query(default=100, ge=1, le=1000), offset: int = Query(default=0, ge=0)):
    cache_key = f'coins:list:limit_{limit}:offset_{offset}'
    cache = await get_cached(cache_key)
    if cache is not None:          
        return cache
    
    data = await get_all_coins(limit, offset)
    await set_cached(cache_key, data) 
    return data

@router.get("/{coingecko_id}", response_model=MarketDataResponse)
@limiter.limit("60/minute")
async def get_coin(request: Request, coingecko_id: str):
    cache_key = f'coin:{coingecko_id}:latest'
    cache = await get_cached(cache_key)

    if cache:
        return cache
    
    data = await get_latest_market_data(coingecko_id)

    if data:
        await set_cached(cache_key, data)
        return data
    
    raise HTTPException(status_code=404, detail=f'Coin with {coingecko_id} not found.')

@router.get("/{coingecko_id}/history", response_model=list[MarketDataResponse])
@limiter.limit("20/minute")
async def get_coin_history(
    request: Request,
    coingecko_id: str,
    start: datetime,
    end: datetime
):
    if start >= end:
        raise HTTPException(status_code=422, detail="start must be before end")
    
    cache_key = f'coin:{coingecko_id}:history:{start.isoformat()}:{end.isoformat()}'
    cache = await get_cached(cache_key)
    if cache is not None:
        return cache
    
    data = await get_market_data_history(coingecko_id, start, end)
    await set_cached(cache_key, data)
    return data