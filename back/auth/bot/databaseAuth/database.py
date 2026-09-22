from motor.motor_asyncio import AsyncIOMotorClient
from back.auth.bot.config.authConfig import MONGO_URI, MONGO_DB_NAME
from datetime import datetime, timedelta, timezone

client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB_NAME]
auth_collection = db['auth_collection']

LOGIN_CODE_TTL = 300  # код входа живет 5 минут


async def ensure_indexes():
    await auth_collection.delete_many({'code': {'$exists': True}, 'expires_at': {'$exists': False}})
    await auth_collection.create_index('user_id', sparse=True)
    await auth_collection.create_index('code', unique=True, sparse=True)
    await auth_collection.create_index('expires_at', expireAfterSeconds=0)

async def find_user(user_id: int, username: str):
    return await auth_collection.find_one({'user_id': user_id, 'username': username})

async def add_OTP(user_id: int, otp: str):
    await auth_collection.update_one(
        {'user_id': user_id},
        {'$set': {'otp': otp}}
        )
    return True

async def register_user(user_id: int, username: str, pswd: str):
    user_data = {
        'user_id': user_id,
        'username': username,
        'pass': pswd,
        'otp': None
    }
    await auth_collection.insert_one(user_data)
    return True

async def isExistOTP(otp: str, user_id: int):
    if not await auth_collection.find_one({'user_id': user_id, 'otp': otp}):
        await add_OTP(user_id=user_id, otp=otp)
        return None
    return False


async def save_login_code(user_id: int, code: str):
    # одноразовый код для входа на сайт
    now = datetime.now(timezone.utc)
    await auth_collection.delete_many({'login_user_id': user_id, 'code': {'$exists': True}})
    await auth_collection.insert_one({
        'code': code,
        'login_user_id': user_id,
        'created_at': now,
        'expires_at': now + timedelta(seconds=LOGIN_CODE_TTL),
        'used': False,
    })
    return True


async def find_login_code(code: str):
    return await auth_collection.find_one({
        'code': code,
        'used': False,
        'expires_at': {'$gt': datetime.now(timezone.utc)},
    })


async def drop_login_code(code: str):
    # код одноразовый, помечаем использованным
    await auth_collection.delete_one({'code': code})
    return True

