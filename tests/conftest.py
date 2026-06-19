import pytest
from fastapi.testclient import TestClient
from app.core.security import get_current_user

from main import app
from app.models.coin import CoinDB
from app.models.market_data import MarketDataDB
from datetime import datetime, UTC


from app.core.rate_limiter import limiter

limiter.enabled = False

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def sample_coin():
    return CoinDB(
        coingecko_id="bitcoin",
        name="Bitcoin",
        symbol="BTC"
    )

@pytest.fixture
def sample_market_data():
    return MarketDataDB(
        coingecko_id="bitcoin",
        current_price=70000.0,
        high_24h=72000.0,
        low_24h=68000.0,
        total_volume=20000000000.0,
        market_cap=1400000000000.0,
        price_change_24h=1500.0,
        recorded_at=datetime.now(UTC)
    )

@pytest.fixture
def coingecko_market_response():
    return [
        {
            "id": "bitcoin",
            "symbol": "btc",
            "name": "Bitcoin",
            "current_price": 70000,
            "high_24h": 72000,
            "low_24h": 68000,
            "total_volume": 20000000000,
            "market_cap": 1400000000000,
            "price_change_24h": 1500,
        }        
    ]

@pytest.fixture
def override_auth():
    fake_user = {"username": "alice", "email": "alice@example.com"}
    app.dependency_overrides[get_current_user] = lambda: fake_user
    yield fake_user
    app.dependency_overrides.clear()   # runs even if the test fails