import json
import asyncio
from app.models.market_data import MarketDataDB
from app.services.repositories.market_data import insert_many_market_data
from datetime import datetime, UTC
from app.services.connections.rabbitmq import rabbitmq_client

async def handle_message(message):
    async with message.process():
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
            recorded_at=datetime.now(UTC)
        )
        for item in raw_data
    ]

        await insert_many_market_data(market_datas)

async def main():
    await rabbitmq_client.setup()
    await rabbitmq_client.consume(handle_message)
    await asyncio.Future()

asyncio.run(main())
