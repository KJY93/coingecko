import pytest
from pydantic import ValidationError
from app.models.coin import CoinDB
from app.models.market_data import MarketDataDB
from datetime import datetime, UTC

def test_coin_db_creates_correctly(sample_coin):
    assert sample_coin.coingecko_id == "bitcoin"
    assert sample_coin.name == "Bitcoin"
    assert sample_coin.symbol == "BTC"

def test_coin_db_model_dump(sample_coin):
    data = sample_coin.model_dump()

    assert isinstance(data, dict)
    assert data["coingecko_id"] == "bitcoin"
    assert data["name"] == "Bitcoin"
    assert data["symbol"] == "BTC"

def test_coin_db_validation_fails_with_missing_field():
    with pytest.raises(ValidationError):
        CoinDB(name="Bitcoin", symbol="BTC")

def test_market_data_optional_fields_can_be_none():
    market_data = MarketDataDB(
        coingecko_id="bitcoin",
        current_price=70000.0,
        high_24h=None,
        low_24h=None,
        total_volume=None,
        market_cap=None,
        price_change_24h=None,
        recorded_at = datetime.now(UTC)
    )

    assert market_data.high_24h is None
    assert market_data.low_24h is None
    assert market_data.current_price == 70000.0

def test_market_data_model_dump_includes_datetime(sample_market_data):
    data = sample_market_data.model_dump()

    assert "recorded_at" in data
    assert isinstance(data["recorded_at"], datetime)
    assert data["current_price"] == 70000.0