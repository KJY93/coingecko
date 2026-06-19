from app.services.coingecko import fetch_market_data, fetch_coins_list
from app.services.cache import get_cached, set_cached, delete_cached
from datetime import datetime, UTC
from app.core.config import settings
import json

async def test_fetch_market_data_calls_correct_endpoint(mocker):
    mock_get_client = mocker.patch("app.services.coingecko.get_coingecko_client")

    mock_client = mocker.MagicMock()
    mock_get_client.return_value = mock_client
    
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = [
        {"coingecko_id": "bitcoin", "current_price": 70000, "market_cap": 1400000000000}
    ]

    mock_client.get = mocker.AsyncMock(return_value=mock_response)

    result = await fetch_market_data(page=1, per_page=100)
    mock_client.get.assert_called_once_with("/coins/markets", params={ "vs_currency": "usd", "page": 1, "per_page": 100})
    assert result == [{"coingecko_id": "bitcoin", "current_price": 70000, "market_cap": 1400000000000}]

async def test_fetch_coins_list_calls_correct_endpoint(mocker):
    mock_get_client = mocker.patch("app.services.coingecko.get_coingecko_client")
    mock_client = mocker.MagicMock()
    mock_get_client.return_value = mock_client

    mock_response = mocker.MagicMock()
    mock_response.json.return_value = [
          { "coingecko_id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin"}
    ]

    mock_client.get = mocker.AsyncMock(return_value=mock_response)
    result = await fetch_coins_list()
    mock_client.get.assert_called_once_with("/coins/list", params={"include_platform": "false"})
    assert result == [
          { "coingecko_id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin"}
    ]

async def test_cache_get_returns_none_for_missing_key(mocker):
    mock_redis = mocker.patch("app.services.cache.redis_client")
    mock_redis.get = mocker.AsyncMock(return_value=None)

    result = await get_cached("missing_key")
    assert result is None

async def test_cache_set_serializes_datetime(mocker):
    mock_redis = mocker.patch("app.services.cache.redis_client")
    mock_redis.set = mocker.AsyncMock(return_value=None)

    dt = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    value = {"recorded_at": dt, "current_price": 70000.0, "coingecko_id": "bitcoin"}
    key = "test_set_key"
    await set_cached(key, value)

    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    stored_key = call_args.args[0]
    stored_json = call_args.args[1]
    stored_ttl = call_args.kwargs["ex"]

    assert stored_key == key
    assert stored_ttl == settings.cache_ttl_seconds

    parsed = json.loads(stored_json)
    assert parsed["recorded_at"] == "2026-06-01 12:00:00+00:00"
    assert parsed["current_price"] == 70000.0  

async def test_cache_delete_key(mocker):
    mock_redis = mocker.patch("app.services.cache.redis_client")
    mock_redis.delete = mocker.AsyncMock(return_value=None)

    key = "test_delete_key"
    await delete_cached(key)
    mock_redis.delete.assert_called_once_with(key)