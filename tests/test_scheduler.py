from app.scheduler.jobs import poll_market_data, poll_coins

async def test_poll_market_data(sample_market_data, mocker):
    fake_page = [ {"id": "bitcoin", "current_price": 70000 } ]
    mock_fetch = mocker.patch("app.scheduler.jobs.fetch_market_data")
    mock_fetch.return_value = fake_page
    
    mock_client = mocker.patch("app.scheduler.jobs.rabbitmq_client")
    mock_client.publish = mocker.AsyncMock()
    mocker.patch("app.scheduler.jobs.asyncio.sleep", new=mocker.AsyncMock())

    await poll_market_data()

    assert mock_fetch.call_count == 5
    assert mock_client.publish.call_count == 5

async def test_poll_coins_transform_data_correctly(mocker):
    fake_response = [ {"id": "bitcoin", "name": "Bitcoin", "symbol": "btc" }, {
        "id": "ethereum", "name": "Ethereum", "symbol": "eth"
    } ]
    mock_fetch = mocker.patch("app.scheduler.jobs.fetch_coins_list")
    mock_fetch.return_value = fake_response

    mock_upsert = mocker.patch("app.scheduler.jobs.upsert_coins")
    await poll_coins()

    mock_upsert.assert_called_once()
    records = mock_upsert.call_args.args[0]
    assert len(records) == 2
    assert records[0].symbol == "BTC"
    assert records[1].symbol == "ETH"


    