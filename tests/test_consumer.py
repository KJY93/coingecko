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
