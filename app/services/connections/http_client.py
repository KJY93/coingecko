import httpx
from app.core.config import settings

_client: httpx.AsyncClient | None = None

def get_coingecko_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=settings.coingecko_base_url,
            headers={"x-cg-demo-api-key": settings.coingecko_apikey},
            timeout=30.0
        )
    return _client

async def close_coingecko_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None