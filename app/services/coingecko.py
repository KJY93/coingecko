from app.services.connections.http_client import get_coingecko_client

async def fetch_market_data(page: int = 1, per_page: int = 100) -> list[dict]:
    client = get_coingecko_client()
    params = { "vs_currency": "usd", "page": page, "per_page": per_page}
    response = await client.get("/coins/markets", params=params)
    response.raise_for_status()
    return response.json()
    
async def fetch_coins_list() -> list[dict]:
    client = get_coingecko_client()
    params = {"include_platform": "false"} 
    response = await client.get("/coins/list", params=params)
    response.raise_for_status()
    return response.json()