from aio_pika import connect_robust, ExchangeType, Message, DeliveryMode
from app.core.config import settings
from typing import Final
import json

EXCHANGE_NAME: Final = "market_data_exchange"
QUEUE_NAME: Final = "market_data"
ROUTING_KEY: Final = "market_data"
class RabbitMQClient:
    def __init__(self):
        self._connection = None
        self._channel = None
        self._exchange = None

    async def get_connection(self):
        if self._connection is None:
            self._connection = await connect_robust(settings.rabbitmq_url)
        return self._connection

    async def close(self):
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def setup(self):
        conn = await self.get_connection()
        self._channel = await conn.channel()
        self._exchange = await self._channel.declare_exchange(EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        queue = await self._channel.declare_queue(QUEUE_NAME, durable=True)
        await queue.bind(self._exchange, routing_key=ROUTING_KEY)
    
    async def publish(self, data):
        message = Message(
            json.dumps(data).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
        )
        await self._exchange.publish(message, routing_key=ROUTING_KEY)


rabbitmq_client = RabbitMQClient()