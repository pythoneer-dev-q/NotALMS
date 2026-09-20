# ! back/server/database/usersDB.py
from back.server.database.client import get_db
from back.server.server_configs.settings import settings
from uuid import uuid4
from back.server.database.utils import hash_password, create_access_token, verify_password
from datetime import datetime, timezone

database = get_db(settings.mongo_cluster)
users = database[settings.mongo_users]
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
        'rating': 0,  # очки за решенные задачи
        'status': True,
        'biography': about_user
    }
    await users.insert_one(document)
    document['_id'] = str(document['_id'])
    return document


async def search_users(user_login: str):
    return await users.find_one({'user_login': user_login}, projection)


# профиль наружу: пароль-хэш не отдаем никогда
PUBLIC_EXCLUDE = {'hashed_password': 0, '_id': 0}


async def public_usersByID(user_uid: str):
    return await users.find_one({'user_uid': user_uid}, PUBLIC_EXCLUDE)


async def search_usersByID(user_uid: str):
    return await users.find_one({'user_uid': user_uid}, PUBLIC_EXCLUDE) if user_uid is not None else None

async def search_usersByTelegram(user_id: int):
    return await users.find_one({'user_telegram_FOR_ANNOUCMENTS': user_id})


async def settg(user_id: int, to_user: str):
    await users.update_one(
        {'user_login': to_user},
        {'$set': {'user_telegram_FOR_ANNOUCMENTS': user_id}}
    )
    return True


async def add_rating(user_uid: str, points: int):
    await users.update_one(
        {'user_uid': user_uid},
        {'$inc': {'rating': points}}
    )


async def rating_position(user_uid: str) -> int:
    # место в топе: сколько юзеров выше
    me = await search_usersByID(user_uid)
    if not me:
        return 0
    above = await users.count_documents({'rating': {'$gt': me.get('rating', 0)}})
    return above + 1


async def leaderboard(limit: int = 10):
    return await users.find(
        {}, projection={
            '_id': 0, 'user_uid': 1, 'user_login': 1,
            'rating': 1, 'name_color': 1
        }
    ).sort('rating', -1).limit(limit).to_list(limit)


# разрешенная палитра для имени
NAME_COLORS = ['#6366f1', '#f472b6', '#4ade80', '#facc15', '#38bdf8', '#f97316', '#a78bfa', '#ef4444']

# темы сайта; midnight = дефолт (не переопределяет базовые :root)
THEMES = ['midnight', 'emerald', 'sunset', 'rose', 'ocean']


async def set_name_color(user_uid: str, color: str):
    await users.update_one(
        {'user_uid': user_uid},
        {'$set': {'name_color': color}}
    )


async def set_theme(user_uid: str, theme: str):
    await users.update_one(
        {'user_uid': user_uid},
        {'$set': {'theme': theme}}
    )


async def unsettg(user_id: int):
    # отвязка telegram от аккаунта
    await users.update_one(
        {'user_telegram_FOR_ANNOUCMENTS': user_id},
        {'$unset': {'user_telegram_FOR_ANNOUCMENTS': ''}}
    )


async def unsettg_by_uid(user_uid: str):
    # отвязка из веба: знаем только uid
    await users.update_one(
        {'user_uid': user_uid},
        {'$unset': {'user_telegram_FOR_ANNOUCMENTS': ''}}
    )


async def admin_users(q: str = ''):
    # для админки: все пользователи, поиск по логину / uid (без хэша пароля)
    flt = {}
    if q and q.strip():
        s = q.strip()
        flt['$or'] = [
            {'user_login': {'$regex': s, '$options': 'i'}},
            {'user_uid': s},
        ]
    docs = await users.find(flt, {'hashed_password': 0}).sort('rating', -1).to_list(length=None)
    return [{**d, '_id': str(d['_id'])} for d in docs]


async def admin_user_by_uid(user_uid: str):
    # полная карточка пользователя для админки
    return await users.find_one(
        {'user_uid': user_uid},
        {'hashed_password': 0, '_id': 0}
    )


async def admin_set_user_status(user_uid: str, status: str):
    # active | blocked — хранится в поле status: True/False
    new_val = (status == 'active')
    await users.update_one(
        {'user_uid': user_uid},
        {'$set': {'status': new_val}}
    )
    return True


def _as_utc(value):
    # время из базы может прийти без tz — приводим к utc
    if not value:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


async def change_username(user_uid: str, new_login: str) -> dict:
    # занято?
    if await users.find_one({'user_login': new_login}, {'user_uid': 1}):
        return {'error': 'логин уже занят'}
    # смена не чаще раза в 3 дня
    user = await users.find_one({'user_uid': user_uid}, {'last_username_change': 1})
    last = _as_utc((user or {}).get('last_username_change'))
    if last is not None:
        left = 3 - (datetime.now(timezone.utc) - last).days
        if left > 0:
            return {'error': f'смена логина доступна раз в 3 дня. подожди ещё {left} дн.'}
    now = datetime.now(timezone.utc).replace(microsecond=0)
    await users.update_one(
        {'user_uid': user_uid},
        {'$set': {'user_login': new_login,
                  'last_username_change': now.isoformat(timespec='seconds', sep='T')}}
    )
    return {'ok': True}



async def delete_user(user_uid: str):
    # каскадное удаление: пользователь + прогресс + прочитанные уроки
    from back.server.database import coursesDB
    await coursesDB.progress.delete_many({'user_uid': user_uid})
    await coursesDB.reads.delete_many({'user_uid': user_uid})
    res = await users.find_one_and_delete({'user_uid': user_uid})
    return res is not None