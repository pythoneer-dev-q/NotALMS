# ! back/server/database/client.py
# один клиент на процесс, общий пул соединений
from motor.motor_asyncio import AsyncIOMotorClient
from back.server.server_configs.settings import settings

client = AsyncIOMotorClient(
    settings.mongo_uri,
    maxPoolSize=settings.mongo_max_pool,
    retryWrites=True,
)
_closed = False


def get_db(name: str):
    return client[name]


def close_client() -> None:
    global _closed
    if _closed:
        return
    _closed = True
    client.close()
