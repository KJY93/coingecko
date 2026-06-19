from fastapi.testclient import TestClient
from main import app
from datetime import datetime

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Gecko API is running"}

def test_list_coins_returns_200(mocker):
    fake_coins = [ {"coingecko_id": "bitcoin", "name": "Bitcoin", "symbol": "BTC"} ]
    mocker.patch("app.api.coins.get_cached", return_value=None)
    mocker.patch("app.api.coins.set_cached")
    mocker.patch("app.api.coins.get_all_coins", return_value=fake_coins)
    response = client.get("/coins/")

    assert response.status_code == 200
    assert response.json() == fake_coins

def test_list_coins_respects_limit_query(mocker):
    mocker.patch("app.api.coins.get_cached", return_value=None)
    mocker.patch("app.api.coins.set_cached")
    mock_get_all = mocker.patch("app.api.coins.get_all_coins", return_value=[])

    response = client.get("/coins/?limit=10&offset=20")
    assert response.status_code == 200
    mock_get_all.assert_called_once_with(10, 20)

def test_list_coins_validates_limit_bounds(mocker):
    assert client.get("/coins/?limit=5000").status_code == 422  
    assert client.get("/coins/?limit=0").status_code == 422      
    assert client.get("/coins/?offset=-5").status_code == 422    

def test_get_coins_returns_404_when_not_found(mocker):
    mocker.patch("app.api.coins.get_cached", return_value=None)
    mocker.patch("app.api.coins.get_latest_market_data", return_value=None)
    response = client.get("/coins/doesnotexistcoin")
    assert response.status_code == 404
    assert response.json()["detail"] == "Coin with doesnotexistcoin not found."

def test_get_coin_returns_data_when_found(mocker):
    fake_data = {
        "coingecko_id": "bitcoin",
        "current_price": 70000.0,
        "recorded_at": "2026-06-01T12:00:00",  
    }
    mocker.patch("app.api.coins.get_cached", return_value=None)
    mocker.patch("app.api.coins.get_latest_market_data", return_value=fake_data)
    mocker.patch("app.api.coins.set_cached", return_value=None)  
    response = client.get("/coins/bitcoin")                        
    assert response.status_code == 200        
    body = response.json()
    assert body["coingecko_id"] == "bitcoin"
    assert body["current_price"] == 70000.0
    assert datetime.fromisoformat(body["recorded_at"]) == datetime.fromisoformat(fake_data["recorded_at"])     

def test_get_coin_history_validates_date_range():
    response = client.get(
        "/coins/bitcoin/history?start=2026-06-10T00:00:00&end=2026-06-01T00:00:00"
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "start must be before end"


    response = client.get(
        "/coins/bitcoin/history?start=2026-06-10T00:00:00&end=2026-06-10T00:00:00"
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "start must be before end"

def test_get_coin_history_returns_empty_list_for_no_data(mocker):
    mocker.patch("app.api.coins.get_cached", return_value=None)
    mocker.patch("app.api.coins.set_cached", return_value=None)
    mocker.patch("app.api.coins.get_market_data_history", return_value=[])

    response = client.get(
        "/coins/bitcoin/history?start=2026-06-01T00:00:00&end=2026-06-10T00:00:00"
    )
    assert response.status_code == 200
    assert response.json() == []

def test_get_coin_history_returns_data(mocker):
    fake_history = [
        { "coingecko_id": "bitcoin", "current_price": 70000.0, "recorded_at": "2026-06-01T12:00:00" },
        { "coingecko_id": "ethereum", "current_price": 80000.0, "recorded_at": "2026-06-01T10:00:00" }
    ]

    mocker.patch("app.api.coins.get_cached", return_value=None)
    mocker.patch("app.api.coins.set_cached", return_value=None)
    mocker.patch("app.api.coins.get_market_data_history", return_value=fake_history)

    response = client.get(
        "/coins/bitcoin/history?start=2026-06-11T00:00:00&end=2026-06-13T00:00:00"
    )

    assert response.status_code == 200
    assert len(response.json()) == 2
    body = response.json()
    assert body[0]["coingecko_id"] == "bitcoin"
    assert body[0]["current_price"] == 70000.0
    assert body[1]["coingecko_id"] == "ethereum"
    assert body[1]["current_price"] == 80000.0
    assert datetime.fromisoformat(body[0]["recorded_at"]) == datetime.fromisoformat(fake_history[0]["recorded_at"])     
    assert datetime.fromisoformat(body[1]["recorded_at"]) == datetime.fromisoformat(fake_history[1]["recorded_at"])  