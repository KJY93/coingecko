from pymongo import UpdateOne

from app.services.connections.mongodb import db
from app.models.coin import CoinDB

async def upsert_coin(coin: CoinDB) -> None:
    query_filter = { 'coingecko_id': coin.coingecko_id }
    update_operation = {
        '$set': coin.model_dump()
    }
    await db.coins.update_one(query_filter, update_operation, upsert=True)

async def upsert_coins(coins: list[CoinDB]) -> None:
    operations = [
        UpdateOne(
            { "coingecko_id": coin.coingecko_id },
            { "$set": coin.model_dump() },
            upsert=True,
            namespace = "gecko.coins"
        )
        for coin in coins
    ]

    if operations:
        await db.coins.bulk_write(operations, ordered=False)

async def get_all_coins(limit: int = 100, offset: int = 0) -> list[dict]:
    return await db.coins.find({}, {"_id": 0}).skip(offset).to_list(length=limit)