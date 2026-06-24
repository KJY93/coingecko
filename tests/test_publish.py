from datetime import datetime, UTC
from app.services.connections.rabbitmq import RabbitMQClient
import json

async def test_publish(mocker):
    client = RabbitMQClient()
    client._exchange = mocker.MagicMock()
    client._exchange.publish = mocker.AsyncMock()

    fake_data = {
        "coingecko_id": "bitcoin",
        "current_price": 70000.0,
        "high_24h": 72000.0,
        "low_24h": 68000.0,
        "total_volume": 20000000000.0,
        "market_cap": 1400000000000.0,
        "price_change_24h": 1500.0,
        "recorded_at": datetime.now(UTC).isoformat()
    }
    await client.publish(fake_data)
    client._exchange.publish.assert_called_once()
    assert client._exchange.publish.call_args.kwargs["routing_key"] == "market_data"
    assert client._exchange.publish.call_args.kwargs["timeout"] == 5.0

async def test_publish_to_retry(mocker):
    client = RabbitMQClient()
    client._channel = mocker.MagicMock()
    client._channel.default_exchange.publish = mocker.AsyncMock()

    await client.publish_to_retry(b"some test bytes", 2)

    sent_message = client._channel.default_exchange.publish.call_args.args[0]
    assert sent_message.headers["x-retry-count"] == 2  
    assert client._channel.default_exchange.publish.call_args.kwargs["routing_key"] == "market_data_retry"