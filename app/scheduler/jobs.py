from app.services.coingecko import fetch_coins_list, fetch_market_data
from app.services.repositories.coin import upsert_coins
from app.models.coin import CoinDB
from app.services.connections.rabbitmq import rabbitmq_client
import logging
import asyncio

logger = logging.getLogger(__name__)
TOTAL_PAGES = 5
PER_PAGE = 100

async def poll_market_data():
    logger.info("Polling market data started")

    for page in range(1, TOTAL_PAGES + 1):
        data = await fetch_market_data(page=page, per_page=PER_PAGE)
        logger.info(f"Fetched page {page}: {len(data)} coins")
        try:
            await rabbitmq_client.publish(data)
            logger.info(f"Published page {page}")
        except Exception as e:
            logger.error(f"Failed to publish page {page}: {e}")

        await asyncio.sleep(2)

    logger.info("Polling market data completed")

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