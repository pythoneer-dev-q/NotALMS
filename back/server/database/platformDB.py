from back.server.database.client import get_db
from back.server.server_configs.settings import settings


database = get_db(settings.mongo_lmscluster)
platform_settings = database[settings.mongo_lmsplatform]
SUPPORT_KEY = 'support'


async def get_support() -> dict:
    document = await platform_settings.find_one({'_id': SUPPORT_KEY}) or {}
    return {
        'email': document.get('email', settings.support_email),
        'telegram': document.get('telegram', settings.support_telegram),
    }


async def set_support(email: str, telegram: str) -> dict:
    payload = {
        'email': (email or '').strip()[:254],
        'telegram': (telegram or '').strip()[:500],
    }
    await platform_settings.update_one(
        {'_id': SUPPORT_KEY}, {'$set': payload}, upsert=True
    )
    return payload
