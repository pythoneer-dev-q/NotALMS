from motor.motor_asyncio import AsyncIOMotorClient
from back.auth.bot.config.authConfig import MONGO_URI, MONGO_DB_NAME
import time

client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB_NAME]
auth_collection = db['auth_collection']

LOGIN_CODE_TTL = 300  # код входа живет 5 минут

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
    await auth_collection.insert_one({
        'code': code,
        'login_user_id': user_id,
        'created_at': int(time.time()),
        'ttl': LOGIN_CODE_TTL,
        'used': False
    })
    return True


async def find_login_code(code: str):
    doc = await auth_collection.find_one({'code': code, 'used': False})
    if not doc:
        return None
    if int(time.time()) - doc.get('created_at', 0) > doc.get('ttl', LOGIN_CODE_TTL):
        return None
    return doc


async def drop_login_code(code: str):
    # код одноразовый, помечаем использованным
    await auth_collection.update_one({'code': code}, {'$set': {'used': True}})
    return True

