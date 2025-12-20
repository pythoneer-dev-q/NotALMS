# ! back/server/database/coursesDB.py
from datetime import timezone, datetime
from motor.motor_asyncio import AsyncIOMotorClient
from server_configs import server_mainConfig as mongo
from typing import Literal, Optional

client = AsyncIOMotorClient(mongo.MONGO_URI)
database = client[mongo.MONGO_LMSCLUSTER]
courses = database[mongo.MONGO_LMSCOURSESDATA]
lessons = database[mongo.MONGO_LMSLESSONS]
progress = database[mongo.MONGO_LMSPROGRESS]
tasks = database[mongo.MONGO_LMSTASKS]
projection = {'_id': 0}


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


async def search_courses(role: str):
    return await courses.find(
        {
            'is_published': True,
            'granted_to': {'$in': ['all', role]}
        },
        projection={
            '_id': 1,
            'title': 1,
            'description': 1
        }
    ).sort('order', 1).to_list(length=None)

async def search_course(role: str, course_id: str):
    return await courses.find_one({
        'granted_to': {'$in': ['all', role]}, '_id': course_id})
async def search_lessons(course_id: str):
    return await lessons.find({'course_id': course_id}).sort('order', 1).to_list(length=None)