from app.services.repositories.coin import upsert_coin, upsert_coins, get_all_coins
from app.services.repositories.market_data import insert_many_market_data, get_market_data_history, get_latest_market_data
from datetime import datetime, UTC

async def test_upsert_coin_calls_update_one_with_upsert(sample_coin, mocker):
    mock_db = mocker.patch("app.services.repositories.coin.db")
    mock_db.coins.update_one = mocker.AsyncMock()

    await upsert_coin(sample_coin)
    mock_db.coins.update_one.assert_called_once()

async def test_upsert_coins_uses_bulk_write(sample_coin, mocker):
    sample_coin_list = [sample_coin]

    mock_db = mocker.patch("app.services.repositories.coin.db")
    mock_db.coins.bulk_write = mocker.AsyncMock()

    await upsert_coins(sample_coin_list)

    mock_db.coins.bulk_write.assert_called_once()

async def test_upsert_coins_handles_empty_list(mocker):
    sample_coin_list = []
    mock_db = mocker.patch("app.services.repositories.coin.db")
    mock_db.coins.bulk_write = mocker.AsyncMock()

    await upsert_coins(sample_coin_list)

    mock_db.coins.bulk_write.assert_not_called()

async def test_get_all_coins_uses_pagination(mocker):
    mock_db = mocker.patch("app.services.repositories.coin.db")

    mock_cursor = mocker.MagicMock()
    mock_db.coins.find.return_value = mock_cursor

    mock_cursor.skip.return_value = mock_cursor

    mock_cursor.to_list = mocker.AsyncMock(return_value=[])
    await get_all_coins(limit=50, offset=10)

    mock_db.coins.find.assert_called_once_with({}, { "_id": 0 })
    mock_cursor.skip.assert_called_once_with(10)
    mock_cursor.to_list.assert_called_once_with(length=50)

async def test_insert_many_market_data_calls(sample_market_data, mocker):
    sample_market_data_list = [sample_market_data]
    mock_db = mocker.patch("app.services.repositories.market_data.db")
    mock_db.market_data.insert_many = mocker.AsyncMock()

    await insert_many_market_data(sample_market_data_list)
    mock_db.market_data.insert_many.assert_called_once_with([m.model_dump() for m in sample_market_data_list])

async def test_insert_many_market_data_calls_with_empty_list(mocker):
    sample_market_data_list = []
    mock_db = mocker.patch("app.services.repositories.market_data.db")
    mock_db.market_data.insert_many = mocker.AsyncMock()

    await insert_many_market_data(sample_market_data_list)
    mock_db.market_data.insert_many.assert_not_called()

async def test_get_market_data_history_filters_by_date_range(mocker):
    start = datetime(2026, 6, 1, tzinfo=UTC)
    end = datetime(2026, 6, 10, tzinfo=UTC)

    mock_db = mocker.patch("app.services.repositories.market_data.db")
    mock_cursor = mocker.MagicMock()
    mock_db.market_data.find.return_value = mock_cursor
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.to_list = mocker.AsyncMock(return_value = [])
    
    await get_market_data_history("bitcoin", start, end)

    mock_db.market_data.find.assert_called_once_with({ "coingecko_id": "bitcoin", "recorded_at": { "$gte": start, "$lte": end} }, {"_id": 0})
    mock_cursor.sort.assert_called_once_with("recorded_at", 1)
    mock_cursor.to_list.assert_called_once_with(length=1000)

async def test_get_market_data_history_returns_empty_for_missing_args(mocker):
    start = datetime(2026, 6, 1, tzinfo=UTC)
    end = datetime(2026, 6, 10, tzinfo=UTC)
    mock_db = mocker.patch("app.services.repositories.market_data.db")
    result = await get_market_data_history("", start, end)

    assert result == []
    mock_db.market_data.find.assert_not_called()

async def test_get_market_data_history_returns_empty_for_missing_start(mocker):
    end = datetime(2026, 6, 10, tzinfo=UTC)
    mock_db = mocker.patch("app.services.repositories.market_data.db")
    result = await get_market_data_history("bitcoin", None, end)

    assert result == []
    mock_db.market_data.find.assert_not_called()

async def test_get_market_data_history_returns_empty_for_missing_end(mocker):
    start = datetime(2026, 6, 10, tzinfo=UTC)
    mock_db = mocker.patch("app.services.repositories.market_data.db")
    result = await get_market_data_history("bitcoin", start, None)

    assert result == []
    mock_db.market_data.find.assert_not_called()

async def test_get_latest_market_data_sorts_desc(mocker):
    mock_db = mocker.patch("app.services.repositories.market_data.db")
    mock_db.market_data.find_one = mocker.AsyncMock(return_value=None)
    await get_latest_market_data("bitcoin")
    mock_db.market_data.find_one.assert_called_once_with(
        {"coingecko_id": "bitcoin"}, {"_id": 0}, sort=[("recorded_at", -1)]
    )