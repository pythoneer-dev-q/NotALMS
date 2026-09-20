# ! back/server/database/client.py
# один клиент на процесс, общий пул соединений
from motor.motor_asyncio import AsyncIOMotorClient
from back.server.server_configs.settings import settings

client = AsyncIOMotorClient(
    settings.mongo_uri,
    maxPoolSize=settings.mongo_max_pool,
    retryWrites=True,
)


def get_db(name: str):
    return client[name]
