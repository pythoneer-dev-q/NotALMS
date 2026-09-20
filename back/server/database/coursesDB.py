# ! back/server/database/coursesDB.py
import time
from datetime import timezone, datetime
from back.server.database.client import get_db
from back.server.database import hotcache
from back.server.server_configs.settings import settings
from typing import Literal, Optional

database = get_db(settings.mongo_lmscluster)
courses = database[settings.mongo_lmscoursesdata]
lessons = database[settings.mongo_lmslessons]
progress = database[settings.mongo_lmsprogress]
tasks = database[settings.mongo_lmstasks]
tests = database[settings.mongo_lmstests]
projection = {'_id': 0}

# кэш в redis (hotcache), ключ по роли
CACHE_PREFIX = 'courses:list:'


async def invalidate_course_cache():
    # сброс после создания/правки курса
    await hotcache.delete_prefix(CACHE_PREFIX)



async def ensure_indexes():
    # индексы под частые запросы
    await courses.create_index('granted_to')
    await courses.create_index('order')
    await lessons.create_index('course_id')
    await tasks.create_index('lesson_id')
    await tests.create_index('task_id')


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
        is_published: bool = True
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
        "description": description,
        "cover": cover,
        "difficulty": difficulty,
        "tags": tags,
        "is_published": is_published,
        "order": order,
        "lessons": lessons,
        "granted_to": granted_to,
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
    task_type: str = 'undefined',
    difficulty: Literal['easy', 'hard'] = 'easy'
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
    if (await lessons.find_one({'_id': _id}) is not None) or (await tasks.find_one({'_id': _id}) is not None):
        raise ValueError(' либо такой урок уже существует, либо такого курса не существует')
    task = {
        "_id": _id,
        "lesson_id": lesson_id,
        "type": task_type,
        "mode": mode,
        "difficulty": difficulty,
        "settings": settings,
        "created_at": timestamp
    }
    await tasks.insert_one(task)
    return task

async def create_test(
    data: dict[str]
):
    doc = {**data, 'created_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat(timespec='seconds', sep='T')}
    await tests.insert_one(doc)
    return doc


async def recent_test(task_def_id: str, minutes: int = 30):
    # недавно сгенерированный вариант этого задания, чтобы не плодить дубли
    border = (datetime.now(timezone.utc).replace(microsecond=0)).timestamp() - minutes * 60
    border_iso = datetime.fromtimestamp(border, timezone.utc).isoformat(timespec='seconds', sep='T')
    return await tests.find_one(
        {'parent_task_id': task_def_id, 'created_at': {'$gte': border_iso}}
    )
async def search_test(task_id: int):
    return await tests.find_one({'task_id': task_id})

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


async def mark_task_solved(user_uid: str, task_id, points: int) -> bool:
    # решенная задача учитывается один раз
    if await progress.find_one({'user_uid': user_uid, 'task_id': task_id}):
        return False
    nowIs = datetime.now(timezone.utc).replace(microsecond=0)
    await progress.insert_one({
        'user_uid': user_uid,
        'task_id': task_id,
        'points': points,
        'created_at': nowIs.isoformat(timespec='seconds', sep='T')
    })
    return True


async def mark_task_hint(user_uid: str, task_id) -> bool:
    # после подсказки задание закрыто: сдать его уже нельзя
    if await progress.find_one({'user_uid': user_uid, 'task_id': task_id}):
        return False
    nowIs = datetime.now(timezone.utc).replace(microsecond=0)
    await progress.insert_one({
        'user_uid': user_uid,
        'task_id': task_id,
        'points': 0,
        'hint': True,
        'created_at': nowIs.isoformat(timespec='seconds', sep='T')
    })
    return True


async def user_progress(user_uid: str):
    return await progress.find(
        {'user_uid': user_uid, 'hint': {'$ne': True}}, {'_id': 0}
    ).sort('created_at', -1).to_list(length=None)


async def user_progress_count(user_uid: str) -> int:
    # только реально решенные, подсказки не считаем
    return await progress.count_documents({'user_uid': user_uid, 'hint': {'$ne': True}})


async def solved_task_ids(user_uid: str) -> set:
    # id задач-определений, уже решенных юзером (без закрытых подсказкой)
    rows = await progress.find(
        {'user_uid': user_uid, 'hint': {'$ne': True}}, {'task_id': 1, '_id': 0}
    ).to_list(length=None)
    return {r['task_id'] for r in rows}


async def hinted_task_ids(user_uid: str) -> set:
    # задачи, закрытые подсказкой
    rows = await progress.find(
        {'user_uid': user_uid, 'hint': True}, {'task_id': 1, '_id': 0}
    ).to_list(length=None)
    return {r['task_id'] for r in rows}


async def closed_task_ids(user_uid: str) -> set:
    # все закрытые задачи (решено + подсказка) — для порядка выдачи
    return await solved_task_ids(user_uid) | await hinted_task_ids(user_uid)


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
    res = await lessons.find_one_and_delete({'_id': lesson_id})
    if res is None:
        return None
    return {**res, '_id': str(res['_id'])}


async def update_task(task_id: str, fields: dict):
    if not fields:
        return None
    fields['updated_at'] = datetime.now(timezone.utc).replace(microsecond=0).isoformat(timespec='seconds', sep='T')
    res = await tasks.find_one_and_update(
        {'_id': task_id}, {'$set': fields}, return_document=True
    )
    if res is None:
        return None
    return {**res, '_id': str(res['_id'])}


async def delete_task(task_id: str):
    # каскад: задача -> сгенеренные варианты (tests)
    await tests.delete_many({'parent_task_id': str(task_id)})
    res = await tasks.find_one_and_delete({'_id': task_id})
    if res is None:
        return None
    return {**res, '_id': str(res['_id'])}


async def admin_all_tasks():
    # для админки: все задачи-определения
    docs = await tasks.find({}).to_list(length=None)
    return [{**d, '_id': str(d['_id'])} for d in docs]