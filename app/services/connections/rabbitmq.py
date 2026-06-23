from aio_pika import connect_robust, ExchangeType, Message, DeliveryMode
from app.core.config import settings
from typing import Final
import json

EXCHANGE_NAME: Final = "market_data_exchange"
QUEUE_NAME: Final = "market_data"
ROUTING_KEY: Final = "market_data"
PREFETCH_COUNT: int = 10
DLX_NAME: Final = "market_data_dlx"
DLQ_NAME: Final = "market_data_dlq"
DLX_ROUTING_KEY: Final = "market_data_dead"
RETRY_QUEUE_NAME: Final = "market_data_retry"
RETRY_DELAY_MS: int = 5000
MAX_RETRIES: Final = 3
class RabbitMQClient:
    def __init__(self):
        self._connection = None
        self._channel = None
        self._exchange = None
        self._queue = None
        self._dlx = None
        self._dlq = None
        self._retry_queue = None

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
        await self._channel.set_qos(prefetch_count=PREFETCH_COUNT)
        self._exchange = await self._channel.declare_exchange(EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)
        self._dlx = await self._channel.declare_exchange(DLX_NAME, ExchangeType.DIRECT, durable=True)
        self._dlq = await self._channel.declare_queue(DLQ_NAME, durable=True)
        await self._dlq.bind(self._dlx, routing_key=DLX_ROUTING_KEY)
        self._queue = await self._channel.declare_queue(QUEUE_NAME, durable=True,
                                                        arguments= {
                                                            "x-dead-letter-exchange": DLX_NAME,
                                                            "x-dead-letter-routing-key": DLX_ROUTING_KEY
                                                        })
        await self._queue.bind(self._exchange, routing_key=ROUTING_KEY)
        # default exchange will publish to retry queue
        self._retry_queue = await self._channel.declare_queue(
            RETRY_QUEUE_NAME,
            durable=True,
            arguments={
                "x-message-ttl": RETRY_DELAY_MS,
                "x-dead-letter-exchange": EXCHANGE_NAME,
                "x-dead-letter-routing-key": ROUTING_KEY  
            }
        )
    
    async def publish(self, data):
        message = Message(
            json.dumps(data).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
        )
        await self._exchange.publish(message, routing_key=ROUTING_KEY)
    
    async def consume(self, callback):
        await self._queue.consume(callback)

    async def publish_to_retry(self, body, retry_count):
        message = Message(
            body,
            delivery_mode=DeliveryMode.PERSISTENT,
            headers={"x-retry-count": retry_count}
        )
        await self._channel.default_exchange.publish(message, routing_key=RETRY_QUEUE_NAME)
 
rabbitmq_client = RabbitMQClient()