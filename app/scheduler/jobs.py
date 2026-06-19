from app.services.coingecko import fetch_coins_list, fetch_market_data
from app.services.repositories.coin import upsert_coins
from app.services.repositories.market_data import insert_many_market_data
from app.models.coin import CoinDB
from app.models.market_data import MarketDataDB
from datetime import datetime, UTC
import logging
import asyncio

logger = logging.getLogger(__name__)
TOTAL_PAGES = 5
PER_PAGE = 100

async def poll_market_data():
    logger.info("Polling market data started")

    all_data = []

    for page in range(1, TOTAL_PAGES + 1):
        data = await fetch_market_data(page=page, per_page=PER_PAGE)
        logger.info(f"Fetched page {page}: {len(data)} coins")
        all_data.extend(data)
        await asyncio.sleep(2)

    market_datas = [
        MarketDataDB(
            coingecko_id=item["id"],
            current_price=item["current_price"],
            high_24h=item.get("high_24h"),       
            low_24h=item.get("low_24h"),           
            total_volume=item.get("total_volume"),
            market_cap=item.get("market_cap"),     
            price_change_24h=item.get("price_change_24h"),  
            recorded_at=datetime.now(UTC)
        )
        for item in all_data
    ]

    await insert_many_market_data(market_datas)
    logger.info(f"Stored {len(market_datas)} market data records (top {TOTAL_PAGES * PER_PAGE})")

async def poll_coins():
    logger.info("Polling coins list started")
    raw_data = await fetch_coins_list()

    logger.info(f"Fetched {len(raw_data)} coins")

    coins = [
        CoinDB(
            coingecko_id=item["id"],
            name=item["name"],
            symbol=item["symbol"].upper()
        )
        for item in raw_data
    ]
    
    await upsert_coins(coins)
    logger.info(f"Upserted {len(coins)} coins")