from app.models.market_data import MarketDataDB
from datetime import datetime
from app.services.connections.mongodb import db


async def insert_many_market_data(records: list[MarketDataDB]) -> None:
    if not records:
        return
    document_list = [ record.model_dump() for record in records ]
    await db.market_data.insert_many(document_list)

async def get_market_data_history(coingecko_id: str, start: datetime, end: datetime, limit: int = 1000) -> list[dict]:
    if not coingecko_id or not start or not end:
        return []

    cursor = db.market_data.find({ "coingecko_id": coingecko_id, "recorded_at": { "$gte": start, "$lte": end} }, {"_id": 0}).sort("recorded_at", 1)
    return await cursor.to_list(length=limit)


async def get_latest_market_data(coingecko_id: str) -> dict | None:
    if not coingecko_id:
        return None
    
    return await db.market_data.find_one( {"coingecko_id": coingecko_id}, {"_id": 0}, sort=[("recorded_at", -1)] )
    