# ! back/server/database/db_init.py
# индексы юзеров, зовется на старте сервера
from back.server.database.client import get_db
from back.server.server_configs.settings import settings


async def ensure_indexes():
    users = get_db(settings.mongo_cluster)[settings.mongo_users]
    await users.create_index('user_login', unique=True)
    await users.create_index('user_telegram_FOR_ANNOUCMENTS')
    await users.create_index([('rating', -1)])

    from back.server.database import coursesDB
    await coursesDB.ensure_indexes()
    # прогресс: одна решенная задача на юзера
    progress = get_db(settings.mongo_lmscluster)[settings.mongo_lmsprogress]
    await progress.create_index(
        [('user_uid', 1), ('task_id', 1)], unique=True
    )
