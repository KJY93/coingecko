from datetime import datetime, UTC
from app.consumer import handle_message
import json

async def test_handle_message_success(mocker, coingecko_market_response):
    mock_insert = mocker.patch("app.consumer.insert_many_market_data", new=mocker.AsyncMock())
    mock_client = mocker.patch("app.consumer.rabbitmq_client")
    mock_client.publish_to_retry = mocker.AsyncMock()
    payload = { "recorded_at": datetime.now(UTC).isoformat(), "coins": coingecko_market_response }
    message = mocker.MagicMock()
    message.body = json.dumps(payload).encode() 
    message.headers = {}
    message.ack = mocker.AsyncMock()
    message.nack = mocker.AsyncMock()

    await handle_message(message)
    mock_insert.assert_called_once()
    message.ack.assert_called_once()
    mock_client.publish_to_retry.assert_not_called()
    message.nack.assert_not_called()

async def test_handle_message_retry(mocker, coingecko_market_response):
    mock_insert = mocker.patch("app.consumer.insert_many_market_data", new=mocker.AsyncMock(side_effect=Exception("some bad thing")))
    mock_client = mocker.patch("app.consumer.rabbitmq_client")
    mock_client.publish_to_retry = mocker.AsyncMock()
    payload = { "recorded_at": datetime.now(UTC).isoformat(), "coins": coingecko_market_response }
    message = mocker.MagicMock()
    message.body = json.dumps(payload).encode() 
    message.headers = { "x-retry-count": 0 }
    message.ack = mocker.AsyncMock()
    message.nack = mocker.AsyncMock()

    await handle_message(message)
    mock_client.publish_to_retry.assert_called_once()
    message.ack.assert_called_once()
    message.nack.assert_not_called()
    mock_insert.assert_called_once()

# can use the Exception method too as in the above
# but here i am simulating something more closer to real production issue
async def test_handle_message_give_up_path(mocker):
    mock_client = mocker.patch("app.consumer.rabbitmq_client")
    mock_client.publish_to_retry = mocker.AsyncMock()
    bad_coins = [ {"symbol": "badcoin" } ]
    payload = { "recorded_at": datetime.now(UTC).isoformat(), "coins": bad_coins }
    message = mocker.MagicMock()
    message.body = json.dumps(payload).encode()
    message.headers = {"x-retry-count": 3}
    message.ack = mocker.AsyncMock()
    message.nack = mocker.AsyncMock()

    await handle_message(message)

    message.nack.assert_called_once_with(requeue=False)
    mock_client.publish_to_retry.assert_not_called()
    message.ack.assert_not_called()

async def test_handle_malformed_message(mocker):
    mock_client = mocker.patch("app.consumer.rabbitmq_client")
    mock_client.publish_to_retry = mocker.AsyncMock()
    message = mocker.MagicMock()
    message.body = b'{"recorded_at": "2026-01-01", "coins": ['
    message.headers = {"x-retry-count": 0}
    message.ack = mocker.AsyncMock()
    message.nack = mocker.AsyncMock()

    await handle_message(message)
    mock_client.publish_to_retry.assert_called_once()
    message.ack.assert_called_once()
    message.nack.assert_not_called()