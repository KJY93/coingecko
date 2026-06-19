import json
from app.services.connections.redis import redis_client
from app.core.config import settings

async def get_cached(key: str) -> dict | list | None:
    result = await redis_client.get(key)
    return json.loads(result) if result else None

async def set_cached(key: str, value: dict | list) -> None:
    json_str = json.dumps(value, default=str)
    await redis_client.set(key, json_str, ex=settings.cache_ttl_seconds)

async def delete_cached(key: str) -> None:
    await redis_client.delete(key)
