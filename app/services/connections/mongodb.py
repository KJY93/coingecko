from app.core.config import settings
from pymongo import AsyncMongoClient

client = AsyncMongoClient(settings.mongodb_url)
db = client[settings.mongodb_db_name]

async def setup_indexes() -> None:
    await db.coins.create_index('coingecko_id', unique=True)

    await db.market_data.create_index([
        ('coingecko_id', 1),
        ('recorded_at', -1)
    ])

    await db.market_data.create_index(
        'recorded_at',
        expireAfterSeconds=7776000
    )

    await db.users.create_index("username", unique=True)
    await db.users.create_index("email")