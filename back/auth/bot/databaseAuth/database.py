from motor.motor_asyncio import AsyncIOMotorClient
from config.authConfig import MONGO_URI, MONGO_DB_NAME

client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGO_DB_NAME]
auth_collection = db['auth_collection']

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

