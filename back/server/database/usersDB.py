# ! back/server/database/usersDB.py
from back.server.database.client import get_db
from back.server.server_configs.settings import settings
from uuid import uuid4
from back.server.database.utils import hash_password, create_access_token, verify_password
from datetime import datetime, timezone
import re
from pymongo.errors import DuplicateKeyError

database = get_db(settings.mongo_cluster)
users = database[settings.mongo_users]
deleted_logins = database[settings.mongo_deleted_logins]
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
        'account_type': 'student',
        'status': True,
        'verified': False,      # галочка «профиль проверен админом»
        'hide_leaderboard': False,  # скрыт из рейтинга (админ видит всегда)
        'biography': about_user
    }
    await users.insert_one(document)
    document['_id'] = str(document['_id'])
    return document


async def search_users(user_login: str):
    login = (user_login or '').strip()
    if not login:
        return None
    return await users.find_one(
        {'user_login': {'$regex': f'^{re.escape(login)}$', '$options': 'i'}},
        projection,
    )


async def login_is_taken(user_login: str, except_uid: str | None = None) -> bool:
    """Проверяет текущие аккаунты и вечный реестр удалённых логинов."""
    login = (user_login or '').strip()
    if not login:
        return False
    current_filter = {
        'user_login': {'$regex': f'^{re.escape(login)}$', '$options': 'i'}
    }
    if except_uid:
        current_filter['user_uid'] = {'$ne': except_uid}
    if await users.find_one(current_filter, {'_id': 1}):
        return True
    return await deleted_logins.find_one(
        {'login_key': login.casefold()}, {'_id': 1}
    ) is not None


async def reserve_deleted_login(user_login: str):
    login = (user_login or '').strip()
    if not login:
        return
    try:
        await deleted_logins.insert_one({
            'login_key': login.casefold(),
            'user_login': login,
            'deleted_at': datetime.now(timezone.utc),
        })
    except DuplicateKeyError:
        pass


# профиль наружу: пароль-хэш не отдаем никогда
PUBLIC_EXCLUDE = {'hashed_password': 0, '_id': 0}


async def public_usersByID(user_uid: str):
    return await users.find_one({'user_uid': user_uid}, PUBLIC_EXCLUDE)


async def search_usersByID(user_uid: str):
    return await users.find_one({'user_uid': user_uid}, PUBLIC_EXCLUDE) if user_uid is not None else None

async def search_usersByTelegram(user_id: int):
    return await users.find_one({'user_telegram_FOR_ANNOUCMENTS': user_id})


async def settg(user_id: int, to_user: str):
    """Привязывает Telegram только к свободному аккаунту.

    Не даём одному Telegram занять два профиля и не перезаписываем уже
    привязанный Telegram другого человека.
    """
    target = await users.find_one(
        {'user_login': {'$regex': f'^{re.escape((to_user or "").strip())}$', '$options': 'i'}}
    )
    if not target:
        return False
    current = await users.find_one({'user_telegram_FOR_ANNOUCMENTS': user_id})
    if current and current.get('user_uid') != target.get('user_uid'):
        return False
    owner = target.get('user_telegram_FOR_ANNOUCMENTS')
    if owner and owner != user_id:
        return False
    result = await users.update_one(
        {'user_uid': target['user_uid']},
        {'$set': {'user_telegram_FOR_ANNOUCMENTS': user_id}}
    )
    return result.matched_count == 1


async def add_rating(user_uid: str, points: int):
    await users.update_one(
        {'user_uid': user_uid},
        [{'$set': {'rating': {'$max': [0, {'$add': [{'$ifNull': ['$rating', 0]}, int(points)]}]}}}]
    )


async def rating_position(user_uid: str, include_hidden: bool = False) -> int:
    """Место в топе.

    Раньше считались все подряд, включая пользователей без решённых задач: у них
    rating = 0, «выше никого нет» → все получали #1. Теперь в рейтинге участвуют
    только те, кто набрал очки, а место = сколько участников строго выше + 1
    (одинаковые очки → одинаковое место).
    """
    me = await search_usersByID(user_uid)
    if not me:
        return 0
    if me.get('account_type') == 'teacher':
        return 0
    rating = int(me.get('rating') or 0)
    if rating <= 0:
        return 0  # не решал задач — в топе не участвует
    above = await users.count_documents({
        **_rank_base_filter(include_hidden),
        'rating': {'$gt': rating},
    })
    return above + 1


def _rank_base_filter(include_hidden: bool = False) -> dict:
    # участники рейтинга: только с очками; скрытых не показываем никому, кроме админа
    flt: dict = {'rating': {'$gt': 0}, 'account_type': {'$ne': 'teacher'}}
    if not include_hidden:
        flt['hide_leaderboard'] = {'$ne': True}
    return flt


def _leaderboard_filter(include_hidden: bool = False, q: str = '', verified_only: bool = False) -> dict:
    flt = _rank_base_filter(include_hidden)
    if q and q.strip():
        s = q.strip()
        flt['$or'] = [
            {'user_login': {'$regex': re.escape(s), '$options': 'i'}},
            {'user_uid': s},
        ]
    if verified_only:
        flt['verified'] = True
    return flt


LB_FIELDS = {
    '_id': 0, 'user_uid': 1, 'user_login': 1, 'rating': 1,
    'name_color': 1, 'verified': 1, 'hide_leaderboard': 1, 'achivements': 1,
    'account_type': 1,
}


async def leaderboard(
    limit: int = 10,
    skip: int = 0,
    include_hidden: bool = False,
    q: str = '',
    verified_only: bool = False,
    with_positions: bool = True,
) -> list[dict]:
    """Топ по очкам с поиском и пагинацией.

    include_hidden=True (админ) — скрытые тоже в списке, с пометкой.
    """
    limit = max(1, min(int(limit or 10), 100))
    skip = max(0, int(skip or 0))
    docs = await users.find(
        _leaderboard_filter(include_hidden, q, verified_only), LB_FIELDS
    ).sort('rating', -1).skip(skip).limit(limit).to_list(limit)

    base = _rank_base_filter(include_hidden)
    out = []
    for d in docs:
        row = dict(d)
        if with_positions:
            above = await users.count_documents({**base, 'rating': {'$gt': int(d.get('rating') or 0)}})
            row['position'] = above + 1
        out.append(row)
    return out


async def leaderboard_count(include_hidden: bool = False, q: str = '', verified_only: bool = False) -> int:
    return await users.count_documents(_leaderboard_filter(include_hidden, q, verified_only))


async def search_users_public(q: str, limit: int = 20, include_hidden: bool = False) -> list[dict]:
    # лёгкий поиск людей по логину (для страницы рейтинга)
    if not q or len(q.strip()) < 2:
        return []
    value = q.strip()
    flt = {'$or': [
        {'user_login': {'$regex': re.escape(value), '$options': 'i'}},
        {'user_uid': value},
    ]}
    if not include_hidden:
        flt['hide_leaderboard'] = {'$ne': True}
    return await users.find(
        flt,
        LB_FIELDS
    ).sort('rating', -1).limit(max(1, min(limit, 50))).to_list(limit)


async def public_profile(user_uid: str, include_hidden: bool = True) -> dict | None:
    # открытая карточка пользователя для страницы /user/{uid}
    doc = await users.find_one({'user_uid': user_uid}, PUBLIC_EXCLUDE)
    if not doc:
        return None
    # Привязка Telegram и причина блокировки не относятся к публичному профилю.
    doc.pop('user_telegram_FOR_ANNOUCMENTS', None)
    doc.pop('blocked_reason', None)
    doc['rank'] = await rating_position(user_uid, include_hidden=include_hidden)
    return doc


async def set_biography(user_uid: str, biography: str):
    # «о себе» — свободный текст, режем по длине
    await users.update_one(
        {'user_uid': user_uid},
        {'$set': {'biography': (biography or '').strip()[:1000]}}
    )
    return True


async def set_leaderboard_hidden(user_uid: str, hidden: bool):
    # скрыть себя из публичного рейтинга
    await users.update_one(
        {'user_uid': user_uid},
        {'$set': {'hide_leaderboard': bool(hidden)}}
    )
    return True



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


async def admin_users(q: str = '', limit: int = 25):
    # Панель не выгружает базу пользователей целиком: поиск обязателен.
    s = (q or '').strip()
    if len(s) < 2:
        return []
    flt = {'$or': [
        {'user_login': {'$regex': re.escape(s), '$options': 'i'}},
        {'user_uid': s},
    ]}
    limit = max(1, min(int(limit or 25), 50))
    docs = await users.find(flt, {'hashed_password': 0}).sort('rating', -1).limit(limit).to_list(length=limit)
    return [{**d, '_id': str(d['_id'])} for d in docs]


async def admin_user_by_uid(user_uid: str):
    # полная карточка пользователя для админки
    return await users.find_one(
        {'user_uid': user_uid},
        {'hashed_password': 0, '_id': 0}
    )


async def admin_set_user_status(user_uid: str, status: str, reason: str | None = None):
    # active | blocked — хранится в поле status: True/False
    new_val = (status == 'active')
    update = {'$set': {'status': new_val}}
    if new_val:
        update['$unset'] = {'blocked_reason': ''}
    else:
        update['$set']['blocked_reason'] = (reason or '').strip()[:500] or 'Нарушение правил платформы'
    await users.update_one({'user_uid': user_uid}, update)
    return True


async def admin_set_user_verified(user_uid: str, verified: bool):
    # галочка «проверен»: профиль подтверждён администратором
    await users.update_one(
        {'user_uid': user_uid},
        {'$set': {'verified': bool(verified)}}
    )
    return True


async def set_password(user_uid: str, password: str) -> bool:
    result = await users.update_one(
        {'user_uid': user_uid},
        {'$set': {'hashed_password': await hash_password(password)}},
    )
    return result.matched_count == 1


async def admin_update_user(user_uid: str, fields: dict) -> bool:
    """Разрешённые поля профиля, которые можно изменить из панели управления."""
    allowed = {'user_login', 'biography', 'name_color', 'hide_leaderboard', 'verified'}
    update = {key: value for key, value in fields.items() if key in allowed}
    if 'user_login' in update:
        update['user_login'] = str(update['user_login']).strip()
    if 'biography' in update:
        update['biography'] = str(update['biography'] or '').strip()[:1000]
    if not update:
        return await users.find_one({'user_uid': user_uid}, {'_id': 1}) is not None
    if 'user_login' in update and await login_is_taken(update['user_login'], except_uid=user_uid):
        return False
    result = await users.update_one({'user_uid': user_uid}, {'$set': update})
    return result.matched_count > 0


async def admin_delete_user(user_uid: str):
    # каскадное удаление админом: юзер + прогресс + прочитанные уроки + подсказки
    from back.server.database import accessDB, coursesDB
    user = await users.find_one({'user_uid': user_uid}, {'user_login': 1})
    if not user:
        return False
    await reserve_deleted_login(user.get('user_login'))
    await coursesDB.progress.delete_many({'user_uid': user_uid})
    await coursesDB.reads.delete_many({'user_uid': user_uid})
    await coursesDB.hints.delete_many({'user_uid': user_uid})
    await coursesDB.tests.delete_many({'owner_uid': user_uid})
    await coursesDB.delete_owned_courses(user_uid)
    await accessDB.delete_user_access(user_uid)
    res = await users.find_one_and_delete({'user_uid': user_uid})
    return res is not None


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
    if await login_is_taken(new_login, except_uid=user_uid):
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
    # каскадное удаление: пользователь + прогресс + прочитанные уроки + подсказки
    from back.server.database import accessDB, coursesDB
    user = await users.find_one({'user_uid': user_uid}, {'user_login': 1})
    if not user:
        return False
    await reserve_deleted_login(user.get('user_login'))
    await coursesDB.progress.delete_many({'user_uid': user_uid})
    await coursesDB.reads.delete_many({'user_uid': user_uid})
    await coursesDB.hints.delete_many({'user_uid': user_uid})
    await coursesDB.tests.delete_many({'owner_uid': user_uid})
    await coursesDB.delete_owned_courses(user_uid)
    await accessDB.delete_user_access(user_uid)
    res = await users.find_one_and_delete({'user_uid': user_uid})
    return res is not None
