# ! back/server/database/usersDB.py
from motor.motor_asyncio import AsyncIOMotorClient
from back.server.server_configs.server_mainConfig import (
        MONGO_URI, MONGO_CLUSTER, MONGO_USERS
)
from uuid import uuid4
from back.server.database.utils import hash_password, create_access_token, verify_password

client = AsyncIOMotorClient(MONGO_URI)
database = client[MONGO_CLUSTER]
users = database[MONGO_USERS]
projection = {'_id': 0}


async def register_user(user_login: str, user_password: str, user_telegram_FOR_ANNOUCMENTS: int, about_user: str = None) -> dict:
    document = {
        'user_uid': str(uuid4()),
        'user_login': user_login,
        'hashed_password': await hash_password(user_password),
        'user_telegram_FOR_ANNOUCMENTS': user_telegram_FOR_ANNOUCMENTS,
        'achivements': [
            {'registered': 'Первый шаг к учебе!'}
        ],
        'status': True,
        'biography': about_user
    }
    await users.insert_one(document)
    document['_id'] = str(document['_id'])
    return document


async def search_users(user_login: str):
    return await users.find_one({'user_login': user_login}, projection)

async def search_usersByID(user_uid: str):
    return await users.find_one({'user_uid': user_uid}, projection) if user_uid is not None else None

async def search_usersByTelegram(user_id: int):
    return await users.find_one({'user_telegram_FOR_ANNOUCMENTS': user_id})


async def settg(user_id: int, to_user: str):
    await users.update_one(
        {'user_login': to_user},
        {'$set': {'user_telegram_FOR_ANNOUCMENTS': user_id}}
    )
    return True