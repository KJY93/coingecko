import json
import logging
import asyncio
from app.models.market_data import MarketDataDB
from app.services.repositories.market_data import insert_many_market_data
from datetime import datetime, UTC
from app.services.connections.rabbitmq import rabbitmq_client, MAX_RETRIES
from app.core.logging import setup_logging


setup_logging()
logger = logging.getLogger(__name__)

async def handle_message(message):
    try:
        raw_data = json.loads(message.body)
        market_datas = [
            MarketDataDB(
                coingecko_id=item["id"],
                current_price=item["current_price"],
                high_24h=item.get("high_24h"),
                low_24h=item.get("low_24h"),
                total_volume=item.get("total_volume"),
                market_cap=item.get("market_cap"),
                price_change_24h=item.get("price_change_24h"),
                recorded_at=datetime.now(UTC),
            )
            for item in raw_data
        ]
        await insert_many_market_data(market_datas)
        await message.ack()
        logger.info(f"Stored {len(market_datas)} records")
    except Exception as e:
        retry_count = (message.headers or {}).get("x-retry-count", 0)
        logger.warning(f"Failed (retry {retry_count}): {e}")
        if retry_count < MAX_RETRIES:
            await rabbitmq_client.publish_to_retry(message.body, retry_count + 1)
            await message.ack()
        else:
            logger.error("Max retries reached, dead-lettering")
            await message.nack(requeue=False)
            
async def main():
    await rabbitmq_client.setup()
    await rabbitmq_client.consume(handle_message)
    logger.info("Consumer started, waiting for messages...")
    await asyncio.Future()

asyncio.run(main())
