from aio_pika import connect_robust
from app.core.config import settings

class RabbitMQClient:
    def __init__(self):
        self._connection = None

    async def get_connection(self):
        if self._connection is None:
            self._connection = await connect_robust(settings.rabbitmq_url)
        return self._connection
    
    async def get_channel(self):
        conn = await self.get_connection()
        return await conn.channel()

    async def close(self):
        if self._connection:
            await self._connection.close()
            self._connection = None

rabbitmq_client = RabbitMQClient()