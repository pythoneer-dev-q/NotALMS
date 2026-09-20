from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse as jsonset
from back.server.handlers.httpbearer import get_current_user
from back.server.database import coursesDB, usersDB
from back.server.handlers.fronthandler_conf import models
from back.server.tasks import biologyUtil
from back.server.server_configs.settings import settings

crouter = APIRouter(prefix='/v1')


def require_admin(x_admin_secret: str | None = Header(None)):
    # админ-действия только с паролем из .env
    if not settings.admin_secret or x_admin_secret != settings.admin_secret:
        raise HTTPException(403, 'admin secret invalid')


@crouter.get('/courses')
async def zagl(user=Depends(get_current_user)):
    return await coursesDB.search_courses(
        role=user['role']
    )

@crouter.get('/getcourse/{courseId}')
async def main_returnCourse(courseId: str, user=Depends(get_current_user)):
    courseData = await coursesDB.search_course(
        role=user['role'],
        course_id=courseId
    )
    return jsonset(
        content=courseData, status_code=200
    )
@crouter.get('/search_lessons/{course_id}')
async def main_lessonSearcher(course_id: str, user=Depends(get_current_user)):
    lessonsData = await coursesDB.search_lessons(
        course_id=course_id
    )
    return jsonset(
        content=lessonsData, status_code=200)
@crouter.get('/gettasks/{Task_LessonId}')
async def main_TaskLessonSearch(Task_LessonId:str, user=Depends(get_current_user)):
    testData = await coursesDB.search_tasks(lesson_id=Task_LessonId)
    return jsonset(
        content=testData, status_code=200
    )
@crouter.post(
    '/createCourse',
    dependencies=[Depends(require_admin)]
)
async def main_courseCreater(
    data: models.RegVisibleCourse
):
    return await coursesDB.create_courseVisible(
        _id=data.id,
        title=data.title,
        lessons=data.lessons,
        granted_to=data.granted_to,
        tags=data.tags,
        order=data.order,
        cover=data.cover,
        description=data.description,
        difficulty=data.difficulty,
        is_published=data.is_published
    )

@crouter.post(
    '/createLesson',
    dependencies=[Depends(require_admin)]
)
async def main_LessonCreater(
    data: models.RegVisibleLesson
):
    return await coursesDB.create_lessonIn(
        _id=data.id,
        course_id=data.course_id,
        title=data.title,
        type_lesson=data.type,
        order=data.order,
        content=data.content
    )
"""
        _id - ид задания,
        lesson_id - привязка к уроку,
        type - тип задания,
        mode - /v1/tasks/{mode} эндпоинт для проверки,
        difficulty - сложность (по умолчанию -- легко),
        settings - настройки для задания {mode}
        created_at - временная метка
    """
@crouter.post('/createTask', dependencies=[Depends(require_admin)])
async def main_taskUpdater(
    data: models.RegVisibleTask
):
    return await coursesDB.create_Test(
        _id=data.id, 
        lesson_id=data.lesson_id,
        mode=data.mode,
        settings=data.settings,
        task_type=data.type_task,
        difficulty=data.difficulty
    )



@crouter.post('/check_answer')
async def main_answerCheck(data: dict, user=Depends(get_current_user)):
    sol = await coursesDB.search_test__id(data['task_id'])
    if not sol:
        return jsonset(content={'error': 'задача не найдена'}, status_code=404)
    # очки только за первое решение определения задачи, а не за перегенерённый вариант
    key = sol.get('parent_task_id') or data['task_id']
    if key in await coursesDB.solved_task_ids(user['user_uid']):
        # повторно решать нельзя: прогресс уже записан
        return jsonset(content={'is_correct': True, 'already_solved': True}, status_code=200)
    if key in await coursesDB.hinted_task_ids(user['user_uid']):
        # подсказка использована — задание закрыто
        return jsonset(content={'closed': True, 'hint_used': True}, status_code=200)
    sub = await biologyUtil.validate_submission(user_input=data['user_input'], solution=sol['internal_solution'])
    if sub.get('is_correct'):
        fresh = await coursesDB.mark_task_solved(
            user['user_uid'], key, sub.get('score', 0)
        )
        if fresh:
            await usersDB.add_rating(user['user_uid'], sub.get('score', 0))
            sub['rating_awarded'] = sub.get('score', 0)
    return jsonset(content=sub, status_code=200)
@crouter.get('/getTest/{click_from}')
async def main_taskGetter(click_from: str, user=Depends(get_current_user)):
    if (tmp := await coursesDB.search_tasks__id(_id=click_from)):
        # задания идут по порядку: сначала решаем предыдущие в этом уроке
        solved = await coursesDB.solved_task_ids(user['user_uid'])
        hinted = await coursesDB.hinted_task_ids(user['user_uid'])
        already = str(tmp['_id']) in solved
        hint_used = str(tmp['_id']) in hinted
        if not already:
            for t in await coursesDB.tasks_in_lesson(tmp['lesson_id']):
                if t['_id'] == tmp['_id']:
                    break  # дошли до текущего — все предыдущие закрыты
                if str(t['_id']) not in solved and str(t['_id']) not in hinted:
                    return jsonset(content={
                        'error': 'сначала реши предыдущие задания этого урока'
                    }, status_code=403)
        # один и тот же вариант держим 30 минут: меньше мусора в базе и стабильные очки
        cached = await coursesDB.recent_test(click_from, minutes=30)
        if cached is None:
            cached = await biologyUtil.generate_task(
                mode=int(tmp['mode']),
                length=int(tmp['settings']['taskLen'])
            )
            cached['parent_task_id'] = str(click_from)
            await coursesDB.create_test(cached)
        # наружу отдаём без ответа и служебных полей
        return jsonset(content={
            'mode': cached.get('mode'),
            'task_id': cached.get('task_id'),
            'condition': cached.get('condition', {}),
            'tryings': cached.get('tryings', 0),
            'solved': already,
            'hint_used': hint_used
        }, status_code=200)
    return jsonset(
        content={
            'error': 'такого урока не существует'
        }, status_code=404
    )


@crouter.get('/solve_task/{task_id}')
async def main_taskSolver(task_id: str, user=Depends(get_current_user)):
    # подсказка: показываем ответ и навсегда закрываем задание
    try:
        tid = int(task_id)  # task_id в базе int, строка не сматчилась бы
    except ValueError:
        return jsonset(content={'error': 'неверный id задачи'}, status_code=400)
    inst = await coursesDB.search_test__id(tid)
    key = (inst or {}).get('parent_task_id') or str(task_id)
    if key in await coursesDB.solved_task_ids(user['user_uid']):
        return jsonset(content={'error': 'задача уже решена, подсказка не нужна'}, status_code=409)
    if key in await coursesDB.hinted_task_ids(user['user_uid']):
        return jsonset(content={'error': 'подсказка уже использована, задание закрыто'}, status_code=409)
    canonical = (inst or {}).get('internal_solution', {}).get('canonical_5_3')
    if canonical is None:
        task = await coursesDB.search_tasks__id(_id=task_id)
        canonical = (task or {}).get('internal_solution', {}).get('canonical_5_3')
    if canonical is None:
        return jsonset(content={'error': 'подсказки для этой задачи нет'}, status_code=404)
    # фиксируем использование подсказки: задание закрывается для юзера
    await coursesDB.mark_task_hint(user['user_uid'], key)
    return jsonset(content={'solution': f"5'-{canonical}-3'", 'closed': True}, status_code=200)


@crouter.get('/me/solved')
async def main_solvedList(user=Depends(get_current_user)):
    # решенные и закрытые подсказкой: фронт красит сайдбар и блокирует повтор
    solved = await coursesDB.solved_task_ids(user['user_uid'])
    hinted = await coursesDB.hinted_task_ids(user['user_uid'])
    return jsonset(content={
        'solved': list(solved),
        'hinted': list(hinted),
        'closed': list(solved | hinted)
    }, status_code=200)


@crouter.post('/lesson/read/{lesson_id}')
async def main_lessonRead(lesson_id: str, user=Depends(get_current_user)):
    # урок прочитан: фронт зовет, когда долистал контент до конца
    fresh = await coursesDB.mark_lesson_read(user['user_uid'], lesson_id)
    return jsonset(content={'ok': True, 'fresh': fresh}, status_code=200)


@crouter.get('/me/reads/{course_id}')
async def main_readList(course_id: str, user=Depends(get_current_user)):
    # какие уроки курса уже прочитаны
    return jsonset(content={'read': list(await coursesDB.read_lesson_ids(user['user_uid'], course_id))}, status_code=200)


@crouter.put('/admin/course/{course_id}', dependencies=[Depends(require_admin)])
async def main_adminCourseUpdate(course_id: str, data: models.AdminCourseUpdate):
    # правка существующего курса из админки
    fields = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    res = await coursesDB.update_course(course_id, fields)
    if res is None:
        return jsonset(content={'error': 'нечего обновлять или курс не найден'}, status_code=404)
    return jsonset(content={'ok': True}, status_code=200)


@crouter.get('/admin/course/{course_id}', dependencies=[Depends(require_admin)])
async def main_adminCourseGet(course_id: str):
    # полная карточка курса для редактора (в т.ч. черновики)
    doc = await coursesDB.search_course_admin(course_id)
    if doc is None:
        return jsonset(content={'error': 'курс не найден'}, status_code=404)
    return jsonset(content=doc, status_code=200)


@crouter.get('/admin/course/{course_id}/lessons', dependencies=[Depends(require_admin)])
async def main_adminLessons(course_id: str):
    # уроки курса для редактора (без jwt, по admin secret)
    docs = await coursesDB.search_lessons(course_id)
    if docs:
        docs = [{**d, '_id': str(d['_id'])} for d in docs]
    return jsonset(content=docs, status_code=200)


@crouter.get('/admin/lesson/{lesson_id}/tasks', dependencies=[Depends(require_admin)])
async def main_adminLessonTasks(lesson_id: str):
    # задачи урока для редактора (без jwt, по admin secret)
    docs = await coursesDB.search_tasks(lesson_id)
    if docs:
        docs = [{**d, '_id': str(d['_id'])} for d in docs]
    return jsonset(content=docs, status_code=200)


@crouter.delete('/admin/course/{course_id}', dependencies=[Depends(require_admin)])
async def main_adminCourseDelete(course_id: str):
    # удаление курса вместе с уроками, задачами и вариантами
    res = await coursesDB.delete_course(course_id)
    if res is None:
        return jsonset(content={'error': 'курс не найден'}, status_code=404)
    return jsonset(content={'ok': True}, status_code=200)


@crouter.put('/admin/lesson/{lesson_id}', dependencies=[Depends(require_admin)])
async def main_adminLessonUpdate(lesson_id: str, data: models.AdminLessonUpdate):
    # правка урока (заголовок, контент-блоки, порядок, тип)
    fields = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    res = await coursesDB.update_lesson(lesson_id, fields)
    if res is None:
        return jsonset(content={'error': 'урок не найден'}, status_code=404)
    return jsonset(content={'ok': True}, status_code=200)


@crouter.delete('/admin/lesson/{lesson_id}', dependencies=[Depends(require_admin)])
async def main_adminLessonDelete(lesson_id: str):
    # удаление урока вместе с задачами и их вариантами
    res = await coursesDB.delete_lesson(lesson_id)
    if res is None:
        return jsonset(content={'error': 'урок не найден'}, status_code=404)
    return jsonset(content={'ok': True}, status_code=200)


@crouter.put('/admin/task/{task_id}', dependencies=[Depends(require_admin)])
async def main_adminTaskUpdate(task_id: str, data: models.AdminTaskUpdate):
    # правка задачи: mode / settings / difficulty / type / привязка к уроку
    raw = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    # в базе поле называется type, а не type_task
    fields = {}
    for k, v in raw.items():
        fields['type' if k == 'type_task' else k] = v
    res = await coursesDB.update_task(task_id, fields)
    if res is None:
        return jsonset(content={'error': 'задача не найдена'}, status_code=404)
    return jsonset(content={'ok': True}, status_code=200)


@crouter.delete('/admin/task/{task_id}', dependencies=[Depends(require_admin)])
async def main_adminTaskDelete(task_id: str):
    # удаление задачи вместе с её сгенерированными вариантами
    res = await coursesDB.delete_task(task_id)
    if res is None:
        return jsonset(content={'error': 'задача не найдена'}, status_code=404)
    return jsonset(content={'ok': True}, status_code=200)


@crouter.get('/lastnews')
async def rtNews():
    return [
        {
            'title': "Провайдер для локального сервера или почему сайт упал?",
            'text': 'За последние пару часов произошло нечто любопытное с провайдером. Подробности <a href="https://t.me/NotALMS/16">В Telegram</a>',
            'emoji': '⚠️',
            'url': 'https://avatars.mds.yandex.net/i?id=7e4846a676fa7b0274b0df9998596bac_l-5233432-images-thumbs&n=13'
        },
        {
        'title': 'Мы обновились!', 
        'text': 'Система NotALMS обновилась! Посмотреть наши новости вы сможете в <a href="https://t.me/NotALMS">✈️ Telegram</a>',
        'url': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQDnUwfncYXorPAjtljnLQ0r31A6Y20kersdw&s', 
        'emoji': '📩'
        },
        {
            'title': 'Ищем ошибки',
            'text': 'Возможны ошибки в работе приложения. Просим сообщать о нахождении таких ошибок в поддержку.',
            'emoji': '💡'
        },
        {
            'title': 'Хотим узнать ваще мнение',
            'text': 'Нам важно, что вы думаете о системе. Просим заполнить этот опросник. Займет не больше 5ти минут. <a href="https://forms.yandex.ru/u/697065b6f47e73b3ab544e35">Заполнить</a>',
            'emoji': '✨'
        },
        {
            'title': "Контакт с разработчиками",
            'text': 'Если вы хотите связаться с нами, напишите <a href="https://desthenq.t.me/">в Telegram</a>',
            'emoji': '🇷🇺'
        },
        {
            'title': "Официальные контакты",
            'text': 'Официальная почта проекта: <a href="mailto:admin_lms@notawallet.sbs">admin_lms@notawallet.sbs</a>',
            'emoji': '🆔',
            'url': 'https://blog.1a23.com/wp-content/uploads/sites/2/2020/02/Desktop.png'
        },
        {
            'title': "Страничка с новостями",
            'text': 'Открыли свою страничку с новостями. Теперь вам будет проще следить за ними <a href="https://news-dc1.lms.notawallet.sbs/">ЗДЕСЬ</a>',
            'emoji': '📰',
            'url': 'https://imgur.com/a/bPfyZtb'
        }
    ]

"https://avatars.mds.yandex.net/i?id=7e4846a676fa7b0274b0df9998596bac_l-5233432-images-thumbs&n=13"