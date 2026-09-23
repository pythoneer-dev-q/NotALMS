# ! back/server/database/coursesDB.py
import time
from datetime import timezone, datetime, timedelta
from back.server.database.client import get_db
from back.server.database import hotcache
from back.server.server_configs.settings import settings
from typing import Literal, Optional
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

database = get_db(settings.mongo_lmscluster)
courses = database[settings.mongo_lmscoursesdata]
lessons = database[settings.mongo_lmslessons]
progress = database[settings.mongo_lmsprogress]
tasks = database[settings.mongo_lmstasks]
tests = database[settings.mongo_lmstests]
attempts = database[settings.mongo_lmsattempts]
projection = {'_id': 0}

# кэш в redis (hotcache), ключ по роли
CACHE_PREFIX = 'courses:list:'


async def invalidate_course_cache():
    # сброс после создания/правки курса
    await hotcache.delete_prefix(CACHE_PREFIX)



async def ensure_indexes():
    # индексы под частые запросы
    # Старые варианты заданий были временными, но не имели TTL и копились бесконечно.
    await tests.delete_many({'expires_at': {'$exists': False}})
    await courses.create_index('granted_to')
    await courses.create_index('owner_uid')
    await courses.create_index('role_ids')
    await courses.create_index('order')
    await lessons.create_index('course_id')
    await tasks.create_index('lesson_id')
    await progress.create_index([('user_uid', 1), ('task_id', 1)], unique=True)
    await progress.create_index('task_id')
    await tests.create_index('task_id')
    await tests.create_index([('parent_task_id', 1), ('owner_uid', 1)])
    await tests.create_index('expires_at', expireAfterSeconds=0)
    await attempts.create_index([('user_uid', 1), ('task_id', 1)], unique=True)
    await attempts.create_index('task_id')
    await hints.create_index([('user_uid', 1), ('task_id', 1)])
    await reads.create_index([('user_uid', 1), ('lesson_id', 1)])


async def create_courseVisible(
        _id: str,
        title: str,
        lessons: list[str],
        granted_to: list[str],
        tags: list[str],
        order: int = -1,
        description: str = 'Описание пока не задано...',
        cover: Optional[str] = '../../../front/assets/imgs/default.png',
        difficulty: Literal['easy', 'hard'] = 'easy',
        is_published: bool = True,
        owner_uid: str | None = None,
        role_ids: list[str] | None = None,
) -> dict | None:
    """ _id - ид курса
        title - заголовок для сайта
        description - описание под карточку
        cover[optional] - обложка для курса
        difficulty - сложность
        lessons[idS] - id уроков для курса
        granted_to - разрешеные группы пользователей
        created_at - временная метка создания обложки курса
    """
    nowIs = datetime.now(timezone.utc).replace(microsecond=0)
    timestamp = nowIs.isoformat(timespec='seconds', sep='T')
    short_info = {
        "_id": _id,
        "title": title,
        "description": str(description or '').strip()[:500],
        "cover": cover,
        "difficulty": difficulty,
        "tags": tags,
        "is_published": is_published,
        "order": order,
        "lessons": lessons,
        "granted_to": granted_to,
        "owner_uid": owner_uid,
        "role_ids": role_ids or [],
        "created_at": timestamp
    }
    await courses.insert_one(short_info)
    await invalidate_course_cache()
    return short_info


async def create_lessonIn(
        _id: str,
        course_id: str,
        title: str,
        content: list[dict],
        type_lesson: Literal['theory', 'test'] = 'theory',
        order: int = -1
) -> dict | None:
    """ | type    | Назначение        |
        | ------- | ----------------- |
        | text    | обычный текст     |
        | image   | изображение       |
        | list    | список            |
        | code    | код               |
        | warning | важное примечание |
    """


    nowIs = datetime.now(timezone.utc).replace(microsecond=0)
    timestamp = nowIs.isoformat(timespec='seconds', sep='T')
    if type_lesson == 'test' or \
        await lessons.find_one({'_id': _id}) is not None or \
            await courses.find_one({'_id': course_id}) is None:
        raise ValueError('Тип неверный (тесты для тестов), либо такой урок уже существует, либо такого курса не существует')
    lesson = {
        "_id": _id,
        "course_id": course_id,
        "title": title,
        "type": type_lesson,
        "order": order,
        "content": content,
        "created_at": timestamp
    }
    await lessons.insert_one(lesson)
    return lesson


async def create_Test(
    _id: str,
    lesson_id: str,
    mode: str,
    settings: dict,
    title: str = '',
    task_type: str = 'undefined',
    difficulty: Literal['easy', 'hard'] = 'easy',
    hint_mode: str = 'solution',
    hint_text: str = '',
):
    """
        _id - ид задания,
        lesson_id - привязка к уроку,
        type - тип задания,
        mode - /v1/tasks/{mode} эндпоинт для проверки,
        difficulty - сложность (по умолчанию -- легко),
        settings - настройки для задания {mode}
        created_at - временная метка
    """
    nowIs = datetime.now(timezone.utc).replace(microsecond=0)
    timestamp = nowIs.isoformat(timespec='seconds', sep='T')
    if await tasks.find_one({'_id': _id}) is not None:
        raise ValueError('задание с таким id уже существует')
    if await lessons.find_one({'_id': lesson_id}) is None:
        raise ValueError('выбранный урок не существует')
    task = {
        "_id": _id,
        "title": title,
        "lesson_id": lesson_id,
        "type": task_type,
        "mode": mode,
        "difficulty": difficulty,
        "settings": settings,
        "hint_mode": hint_mode,
        "hint_text": hint_text,
        "created_at": timestamp
    }
    await tasks.insert_one(task)
    return task

async def create_test(
    data: dict[str]
):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    owner_filter = {
        'parent_task_id': str(data.get('parent_task_id', '')),
        'owner_uid': data.get('owner_uid'),
    }
    if owner_filter['parent_task_id'] and owner_filter['owner_uid']:
        await tests.delete_many(owner_filter)
    doc = {
        **data,
        'created_at': now,
        'expires_at': now + timedelta(hours=1),
    }
    await tests.insert_one(doc)
    return doc


async def recent_test(task_def_id: str, owner_uid: str = None, minutes: int = 30):
    # недавно сгенерированный вариант этого задания у этого же юзера
    border = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=minutes)
    flt = {'parent_task_id': task_def_id, 'created_at': {'$gte': border}}
    if owner_uid is not None:
        flt['owner_uid'] = owner_uid
    return await tests.find_one(flt)

async def search_test(task_id: int):
    return await tests.find_one({'task_id': task_id})


async def wrong_attempts(user_uid: str, task_id: str) -> int:
    row = await attempts.find_one(
        {'user_uid': user_uid, 'task_id': str(task_id)},
        {'wrong_attempts': 1},
    )
    return int((row or {}).get('wrong_attempts', 0))


async def register_wrong_attempt(user_uid: str, task_id: str,
                                 limit: int = 0) -> int | None:
    """Atomically increment errors, or return None when the configured limit is reached."""
    key = {'user_uid': user_uid, 'task_id': str(task_id)}
    flt = dict(key)
    if limit > 0:
        flt['wrong_attempts'] = {'$lt': limit}
    stamp = datetime.now(timezone.utc).replace(microsecond=0)
    updated = await attempts.find_one_and_update(
        flt,
        {'$inc': {'wrong_attempts': 1}, '$set': {'updated_at': stamp}},
        return_document=ReturnDocument.AFTER,
    )
    if updated:
        return int(updated.get('wrong_attempts', 0))

    existing = await attempts.find_one(key, {'wrong_attempts': 1})
    if existing:
        return None if limit > 0 and int(existing.get('wrong_attempts', 0)) >= limit \
            else int(existing.get('wrong_attempts', 0))

    try:
        await attempts.insert_one({
            **key, 'wrong_attempts': 1,
            'created_at': stamp, 'updated_at': stamp,
        })
        return 1
    except DuplicateKeyError:
        # Another request inserted the counter between find and insert.
        return await register_wrong_attempt(user_uid, task_id, limit)

async def search_courses(role: str):
    # сначала горячий кэш (redis -> память)
    ttl = settings.cache_ttl
    key = f'{CACHE_PREFIX}{role}'
    if ttl > 0:
        hit = await hotcache.get_json(key)
        if hit is not None:
            return hit
    result = await courses.find(
        {
            'is_published': True,
            'granted_to': {'$in': ['all', role]}
        },
        projection={
            '_id': 1,
            'title': 1,
            'description': 1,
            'difficulty': 1,
            'tags': 1
        }
    ).sort('order', 1).to_list(length=None)
    result = [{**c, '_id': str(c['_id'])} for c in result]
    if ttl > 0:
        await hotcache.set_json(key, result, ttl)
    return result

async def search_course(role: str, course_id: str):
    return await courses.find_one({
        'granted_to': {'$in': ['all', role]}, '_id': course_id})


async def courses_for_user(user: dict) -> list[dict]:
    """Return only courses the authenticated account may open."""
    from back.server.database import accessDB

    if user.get('account_type') == 'teacher':
        flt = {'owner_uid': user['user_uid']}
    else:
        role_ids = await accessDB.user_role_ids(user['user_uid'])
        flt = {
            'is_published': True,
            '$or': [
                {'granted_to': {'$in': ['all', 'user']}},
                {'role_ids': {'$in': role_ids}},
            ],
        }
    docs = await courses.find(flt, {
        '_id': 1, 'title': 1, 'description': 1, 'difficulty': 1,
        'tags': 1, 'cover': 1, 'is_published': 1, 'owner_uid': 1,
        'role_ids': 1, 'order': 1,
    }).sort('order', 1).to_list(None)
    return [{**doc, '_id': str(doc['_id'])} for doc in docs]


async def course_for_user(user: dict, course_id: str) -> dict | None:
    if user.get('account_type') == 'teacher':
        flt = {'_id': course_id, 'owner_uid': user['user_uid']}
    else:
        from back.server.database import accessDB
        role_ids = await accessDB.user_role_ids(user['user_uid'])
        flt = {
            '_id': course_id,
            'is_published': True,
            '$or': [
                {'granted_to': {'$in': ['all', 'user']}},
                {'role_ids': {'$in': role_ids}},
            ],
        }
    return await courses.find_one(flt)


async def course_for_lesson(user: dict, lesson_id: str) -> dict | None:
    lesson = await lessons.find_one({'_id': lesson_id}, {'course_id': 1})
    return await course_for_user(user, lesson['course_id']) if lesson else None


async def course_for_task(user: dict, task_id: str) -> dict | None:
    task = await tasks.find_one({'_id': task_id}, {'lesson_id': 1})
    return await course_for_lesson(user, task['lesson_id']) if task else None


async def teacher_courses(owner_uid: str) -> list[dict]:
    docs = await courses.find({'owner_uid': owner_uid}).sort('order', 1).to_list(None)
    return [{**doc, '_id': str(doc['_id'])} for doc in docs]


async def course_scope_ids(role_id: str, owner_uid: str) -> list[str]:
    rows = await courses.find(
        {'owner_uid': owner_uid, 'role_ids': role_id}, {'_id': 1}
    ).to_list(None)
    return [str(row['_id']) for row in rows]


async def task_ids_for_courses(course_ids: list[str]) -> list[str]:
    if not course_ids:
        return []
    lesson_ids = [row['_id'] for row in await lessons.find(
        {'course_id': {'$in': course_ids}}, {'_id': 1}
    ).to_list(None)]
    if not lesson_ids:
        return []
    return [str(row['_id']) for row in await tasks.find(
        {'lesson_id': {'$in': lesson_ids}}, {'_id': 1}
    ).to_list(None)]


async def clear_user_course_progress(user_uid: str, course_ids: list[str]):
    task_ids = await task_ids_for_courses(course_ids)
    lesson_ids = [row['_id'] for row in await lessons.find(
        {'course_id': {'$in': course_ids}}, {'_id': 1}
    ).to_list(None)] if course_ids else []
    if task_ids:
        point_rows = await progress.find(
            {'user_uid': user_uid, 'task_id': {'$in': task_ids}}
        ).to_list(None)
        await progress.delete_many({'user_uid': user_uid, 'task_id': {'$in': task_ids}})
        await hints.delete_many({'user_uid': user_uid, 'task_id': {'$in': task_ids}})
        await tests.delete_many({'owner_uid': user_uid, 'parent_task_id': {'$in': task_ids}})
        await attempts.delete_many({'user_uid': user_uid, 'task_id': {'$in': task_ids}})
        removed_points = sum(total_points_for_row(row) for row in point_rows)
        if removed_points:
            from back.server.database import usersDB
            await usersDB.add_rating(user_uid, -removed_points)
    if lesson_ids:
        await reads.delete_many({'user_uid': user_uid, 'lesson_id': {'$in': lesson_ids}})


async def delete_owned_courses(owner_uid: str):
    ids = [str(row['_id']) for row in await courses.find({'owner_uid': owner_uid}, {'_id': 1}).to_list(None)]
    for course_id in ids:
        await delete_course(course_id)


async def delete_progress_for_tasks(task_ids: list[str]):
    if not task_ids:
        return
    rows = await progress.find({'task_id': {'$in': task_ids}}).to_list(None)
    totals = {}
    for row in rows:
        totals[row['user_uid']] = totals.get(row['user_uid'], 0) + total_points_for_row(row)
    await progress.delete_many({'task_id': {'$in': task_ids}})
    if totals:
        from back.server.database import usersDB
        for user_uid, points in totals.items():
            await usersDB.add_rating(user_uid, -points)


async def search_course_admin(course_id: str):
    # админская выборка: полный документ курса вне зависимости от granted_to
    doc = await courses.find_one({'_id': course_id})
    if doc is None:
        return None
    return {**doc, '_id': str(doc['_id'])}
async def search_lessons(course_id: str):
    return await lessons.find({'course_id': course_id}).sort('order', 1).to_list(length=None)
async def search_tasks(lesson_id: str):
    return await tasks.find({'lesson_id': lesson_id}).to_list(length=None)
async def search_tasks_public(lesson_id: str):
    return await tasks.find(
        {'lesson_id': lesson_id},
        {'settings': 0, 'hint_text': 0, 'internal_solution': 0},
    ).to_list(length=None)
async def search_tasks__id(_id: str):
    return await tasks.find_one({'_id': _id})
async def search_test__id(task_id: int):
    return await tests.find_one({'task_id': task_id}, projection)


async def search_lesson(lesson_id: str):
    doc = await lessons.find_one({'_id': lesson_id})
    if doc is None:
        return None
    return {**doc, '_id': str(doc['_id'])}


async def search_task(_id: str):
    doc = await tasks.find_one({'_id': _id})
    if doc is None:
        return None
    return {**doc, '_id': str(doc['_id'])}


# награда за задания: каждое следующее решение дороже в 2 раза, потолок 1000 очков
BASE_TASK_REWARD = 100
MAX_TASK_REWARD = 1000


def reward_for(base_points: int, solve_index: int) -> int:
    # награда за (solve_index+1)-е решение: 100, 200, 400, 800, 1000, 1000...
    return min(base_points * (2 ** solve_index), MAX_TASK_REWARD)


def total_points_for_row(row: dict) -> int:
    if row.get('total_points') is not None:
        return int(row.get('total_points') or 0)
    solves = int(row.get('solve_count') or 0)
    base = int(row.get('base_points') or BASE_TASK_REWARD)
    return sum(reward_for(base, index) for index in range(solves)) or int(row.get('points') or 0)


async def task_solves(user_uid: str, task_id) -> int:
    # сколько раз юзер уже решал это задание (только самостоятельные решения)
    row = await progress.find_one(
        {'user_uid': user_uid, 'task_id': task_id, 'hint': {'$ne': True}}, {'solve_count': 1}
    )
    return int((row or {}).get('solve_count', 0))


async def mark_task_solved(user_uid: str, task_id, base_points: int = BASE_TASK_REWARD,
                           hint: bool = False) -> tuple[int, int]:
    """Записывает решение задания.

    hint=True — задача решена с открытой подсказкой: НЕ создаёт «решено»,
    очков не даёт и не увеличивает счётчик решений. Такие задания живут
    только в коллекции подсказок (hints), поэтому статистика «решено»
    их не учитывает.
    """
    existing = await progress.find_one({'user_uid': user_uid, 'task_id': task_id, 'hint': {'$ne': True}})
    solve_count = int((existing or {}).get('solve_count', 0))
    if hint:
        # с подсказкой: ничего не начисляем и не трогаем прогресс
        return 0, solve_count

    base = int(base_points or BASE_TASK_REWARD)
    reward = reward_for(base, solve_count)
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat(timespec='seconds', sep='T')
    if existing:
        total_points = total_points_for_row(existing) + reward
        await progress.update_one(
            {'_id': existing['_id']},
            {'$set': {'points': reward, 'total_points': total_points, 'base_points': base, 'solve_count': solve_count + 1, 'created_at': stamp}}
        )
    else:
        await progress.insert_one({
            'user_uid': user_uid,
            'task_id': task_id,
            'points': reward,
            'total_points': reward,
            'base_points': base,
            'solve_count': 1,
            'created_at': stamp
        })
    return reward, solve_count + 1


async def drop_tests_for(task_def_id: str, owner_uid: str = None):
    # после верного ответа вариант отработан: в следующий раз дадим новое задание
    flt = {'parent_task_id': str(task_def_id)}
    if owner_uid is not None:
        flt['owner_uid'] = owner_uid
    await tests.delete_many(flt)



# ===== использованные подсказки =====
hints = database[settings.mongo_lmshints]


async def mark_task_hint(user_uid: str, task_id) -> bool:
    # подсказка не блокирует задание: факт использования храним отдельно от прогресса
    if await hints.find_one({'user_uid': user_uid, 'task_id': task_id}):
        return False
    await hints.insert_one({
        'user_uid': user_uid,
        'task_id': task_id,
        'created_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(timespec='seconds', sep='T')
    })
    return True


async def hinted_task_ids(user_uid: str) -> set:
    rows = await hints.find({'user_uid': user_uid}, {'task_id': 1, '_id': 0}).to_list(length=None)
    return {r['task_id'] for r in rows}



async def user_progress(user_uid: str):
    return await progress.find(
        {'user_uid': user_uid, 'hint': {'$ne': True}}, {'_id': 0}
    ).sort('created_at', -1).to_list(length=None)


async def user_progress_count(user_uid: str) -> int:
    # только реально решенные, подсказки не считаем
    return await progress.count_documents({'user_uid': user_uid, 'hint': {'$ne': True}})


async def solved_task_ids(user_uid: str) -> set:
    # id задач-определений, уже решенных юзером (включая повторы — для бесконечных заданий)
    rows = await progress.find(
        {'user_uid': user_uid, 'hint': {'$ne': True}}, {'task_id': 1, '_id': 0}
    ).to_list(length=None)
    return {r['task_id'] for r in rows}


async def closed_task_ids(user_uid: str) -> set:
    # для разблокировки следующих заданий: самостоятельное решение ИЛИ подсказка
    return (await solved_task_ids(user_uid)) | (await hinted_task_ids(user_uid))


async def user_stats(user_uid: str) -> dict:
    """Раздельная статистика: решено без подсказок / решено с подсказкой / всего закрыто."""
    solved = await solved_task_ids(user_uid)
    hinted = await hinted_task_ids(user_uid)
    return {
        'solved': len(solved),            # самостоятельные решения (дают очки)
        'hinted': len(hinted - solved),   # решено/открыто с подсказкой — очков нет
        'closed': len(solved | hinted),   # всё, что закрыто в курсах
    }


async def tasks_in_lesson(lesson_id: str):
    # порядок задач = порядок вставки в базу ($natural)
    return await tasks.find({'lesson_id': lesson_id}).to_list(length=None)


# ===== прочитанные уроки =====
reads = database[settings.mongo_lmsreads]


async def mark_lesson_read(user_uid: str, lesson_id: str) -> bool:
    if await reads.find_one({'user_uid': user_uid, 'lesson_id': lesson_id}):
        return False
    await reads.insert_one({
        'user_uid': user_uid,
        'lesson_id': lesson_id,
        'created_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(timespec='seconds', sep='T')
    })
    return True


async def read_lesson_ids(user_uid: str, course_id: str) -> set:
    lesson_ids = [l['_id'] for l in await search_lessons(course_id)]
    if not lesson_ids:
        return set()
    rows = await reads.find(
        {'user_uid': user_uid, 'lesson_id': {'$in': lesson_ids}},
        {'lesson_id': 1, '_id': 0}
    ).to_list(length=None)
    return {r['lesson_id'] for r in rows}


# ===== админ: правка и удаление курса =====
async def update_course(course_id: str, fields: dict):
    # пустой апдейт не шлем
    if not fields:
        return None
    if 'description' in fields:
        fields['description'] = str(fields['description'] or '').strip()[:500]
    fields['updated_at'] = datetime.now(timezone.utc).replace(microsecond=0).isoformat(timespec='seconds', sep='T')
    res = await courses.find_one_and_update(
        {'_id': course_id}, {'$set': fields}, return_document=True
    )
    await invalidate_course_cache()
    if res is None:
        return None
    return {**res, '_id': str(res['_id'])}


async def delete_course(course_id: str):
    # каскад: курс -> уроки -> задачи -> сгенеренные варианты
    lessons_docs = await lessons.find({'course_id': course_id}, {'_id': 1}).to_list(length=None)
    lesson_ids = [l['_id'] for l in lessons_docs]
    task_ids = []
    if lesson_ids:
        task_ids = [t['_id'] for t in await tasks.find(
            {'lesson_id': {'$in': lesson_ids}}, {'_id': 1}
        ).to_list(length=None)]
    if lesson_ids:
        await lessons.delete_many({'_id': {'$in': lesson_ids}})
    if task_ids:
        await tasks.delete_many({'_id': {'$in': task_ids}})
        await tests.delete_many({'parent_task_id': {'$in': [str(t) for t in task_ids]}})
        await attempts.delete_many({'task_id': {'$in': [str(t) for t in task_ids]}})
        await delete_progress_for_tasks([str(t) for t in task_ids])
        await hints.delete_many({'task_id': {'$in': [str(t) for t in task_ids]}})
    if lesson_ids:
        await reads.delete_many({'lesson_id': {'$in': lesson_ids}})
    res = await courses.find_one_and_delete({'_id': course_id})
    await invalidate_course_cache()
    return res


async def admin_all_courses():
    # для админки: все курсы, включая черновики
    docs = await courses.find({}).sort('order', 1).to_list(length=None)
    return [{**d, '_id': str(d['_id'])} for d in docs]


# ===== админ: правка и удаление уроков/задач =====
async def update_lesson(lesson_id: str, fields: dict):
    if not fields:
        return None
    fields['updated_at'] = datetime.now(timezone.utc).replace(microsecond=0).isoformat(timespec='seconds', sep='T')
    res = await lessons.find_one_and_update(
        {'_id': lesson_id}, {'$set': fields}, return_document=True
    )
    if res is None:
        return None
    return {**res, '_id': str(res['_id'])}


async def delete_lesson(lesson_id: str):
    # каскад: урок -> задачи -> сгенеренные варианты
    task_ids = [t['_id'] for t in await tasks.find(
        {'lesson_id': lesson_id}, {'_id': 1}
    ).to_list(length=None)]
    if task_ids:
        await tasks.delete_many({'_id': {'$in': task_ids}})
        await tests.delete_many({'parent_task_id': {'$in': [str(t) for t in task_ids]}})
        await attempts.delete_many({'task_id': {'$in': [str(t) for t in task_ids]}})
        await delete_progress_for_tasks([str(t) for t in task_ids])
        await hints.delete_many({'task_id': {'$in': [str(t) for t in task_ids]}})
    await reads.delete_many({'lesson_id': lesson_id})
    res = await lessons.find_one_and_delete({'_id': lesson_id})
    if res is None:
        return None
    return {**res, '_id': str(res['_id'])}


async def update_task(task_id: str, fields: dict):
    if not fields:
        return None
    if 'lesson_id' in fields and await lessons.find_one({'_id': fields['lesson_id']}) is None:
        raise ValueError('выбранный урок не существует')
    fields['updated_at'] = datetime.now(timezone.utc).replace(microsecond=0).isoformat(timespec='seconds', sep='T')
    res = await tasks.find_one_and_update(
        {'_id': task_id}, {'$set': fields}, return_document=True
    )
    if res is not None and ({'settings', 'type', 'mode'} & fields.keys()):
        await tests.delete_many({'parent_task_id': str(task_id)})
    if res is None:
        return None
    return {**res, '_id': str(res['_id'])}


async def delete_task(task_id: str):
    # каскад: задача -> сгенеренные варианты (tests)
    await tests.delete_many({'parent_task_id': str(task_id)})
    await attempts.delete_many({'task_id': str(task_id)})
    await delete_progress_for_tasks([str(task_id)])
    await hints.delete_many({'task_id': str(task_id)})
    res = await tasks.find_one_and_delete({'_id': task_id})
    if res is None:
        return None
    return {**res, '_id': str(res['_id'])}


async def admin_all_tasks():
    # для админки: все задачи-определения
    docs = await tasks.find({}).to_list(length=None)
    return [{**d, '_id': str(d['_id'])} for d in docs]
