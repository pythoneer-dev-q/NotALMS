from fastapi import APIRouter, Depends, Header, HTTPException
import hashlib
import inspect
import secrets
from fastapi.responses import JSONResponse as jsonset
from back.server.handlers.httpbearer import get_current_user
from back.server.database import coursesDB, usersDB, newsDB, platformDB
from back.server.handlers.fronthandler_conf import models
from back.server.tasks import biologyUtil, mathUtil
from back.server.server_configs.settings import settings

crouter = APIRouter(prefix='/v1')

# типы заданий, которые проверяет математический мини-инструмент
MATH_TYPES = {'math', 'mathematics', 'arithmetic', 'математика', 'арифметика'}


def _is_math(task_type) -> bool:
    return (task_type or '').strip().lower() in MATH_TYPES


def _max_wrong_attempts(task_def: dict) -> int:
    settings_ = task_def.get('settings') or {}
    if not isinstance(settings_, dict):
        return 0
    try:
        value = int(settings_.get('max_wrong_attempts') or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, min(value, 100))


def _one_variant_per_student(task_def: dict) -> bool:
    settings_ = task_def.get('settings') or {}
    return isinstance(settings_, dict) \
        and str(task_def.get('type') or '').strip().lower() == 'quiz' \
        and settings_.get('one_variant_per_student', True) is not False


async def _generate_variant(task_def: dict, variant_key: str | None = None) -> dict:
    """Вариант задания генерирует нужный мини-инструмент по типу задачи."""
    task_type = (task_def.get('type') or '').strip().lower()
    settings_ = task_def.get('settings') or {}
    if task_type == 'quiz':
        variants = settings_.get('variants') or []
        if not variants:
            raise ValueError('quiz has no variants')
        if variant_key and _one_variant_per_student(task_def):
            digest = hashlib.sha256(variant_key.encode('utf-8')).digest()
            variant = variants[int.from_bytes(digest[:8], 'big') % len(variants)]
        else:
            variant = secrets.choice(variants)
        answers = list(variant.get('answers') or [])
        secrets.SystemRandom().shuffle(answers)
        public_answers = [
            {'id': str(answer.get('id', index)),
             'text': str(answer.get('text', ''))}
            for index, answer in enumerate(answers)
        ]
        correct = [
            str(answer.get('id', index)) for index, answer in enumerate(answers)
            if answer.get('correct') is True
        ]
        return {
            'mode': 'quiz',
            'task_id': secrets.randbelow(900000000) + 100000000,
            'condition': {
                'question': str(variant.get('question', '')),
                'answers': public_answers,
                'multiple': bool(variant.get('multiple') or len(correct) > 1),
            },
            'internal_solution': {'kind': 'quiz', 'correct': correct},
            'tryings': 0,
        }
    if _is_math(task_type):
        return await mathUtil.generate_task(
            mode=int(task_def.get('mode') or mathUtil.MODE_ADDITION),
            difficulty=task_def.get('difficulty') or 'easy',
            settings=settings_,
        )
    return await biologyUtil.generate_task(
        mode=int(task_def.get('mode') or 1),
        length=int(settings_.get('taskLen') or 18),
    )


async def _validate_submission(task_type, user_input, solution: dict):
    if (task_type or '').strip().lower() == 'quiz':
        selected = user_input if isinstance(user_input, list) else [user_input]
        selected = {str(value) for value in selected if value is not None}
        correct = {str(value) for value in solution.get('correct', [])}
        result = {'is_correct': selected == correct,
                  'score': coursesDB.BASE_TASK_REWARD}
    elif _is_math(task_type):
        result = mathUtil.validate_submission(
            user_input=user_input, solution=solution)
    else:
        result = biologyUtil.validate_submission(
            user_input=user_input, solution=solution)
    return await result if inspect.isawaitable(result) else result


def require_admin(x_admin_secret: str | None = Header(None)):
    # админ-действия только с паролем из .env
    if not settings.admin_secret or x_admin_secret != settings.admin_secret:
        raise HTTPException(403, 'admin secret invalid')
    return {'role': 'admin'}


@crouter.get('/courses')
async def zagl(user=Depends(get_current_user)):
    return await coursesDB.courses_for_user(user)


@crouter.get('/getcourse/{courseId}')
async def main_returnCourse(courseId: str, user=Depends(get_current_user)):
    courseData = await coursesDB.course_for_user(user, courseId)
    if courseData is None:
        raise HTTPException(404, 'course not found')
    return jsonset(
        content=courseData, status_code=200
    )


@crouter.get('/search_lessons/{course_id}')
async def main_lessonSearcher(course_id: str, user=Depends(get_current_user)):
    if not await coursesDB.course_for_user(user, course_id):
        raise HTTPException(404, 'course not found')
    lessonsData = await coursesDB.search_lessons(
        course_id=course_id
    )
    return jsonset(
        content=lessonsData, status_code=200)


@crouter.get('/gettasks/{Task_LessonId}')
async def main_TaskLessonSearch(Task_LessonId: str, user=Depends(get_current_user)):
    if not await coursesDB.course_for_lesson(user, Task_LessonId):
        raise HTTPException(404, 'lesson not found')
    testData = await coursesDB.search_tasks_public(lesson_id=Task_LessonId)
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
        is_published=data.is_published,
        role_ids=data.role_ids,
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
@crouter.post('/admin/task', dependencies=[Depends(require_admin)])
async def main_taskCreate(
    data: models.RegVisibleTask
):
    task_id = data.id.strip()
    lesson_id = data.lesson_id.strip()
    mode = data.mode.strip()
    task_type = data.type_task.strip()
    if not task_id or not lesson_id or not mode or not task_type:
        return jsonset(content={'error': 'заполните id, урок, mode и тип задания'}, status_code=400)
    if data.difficulty not in {'easy', 'hard'}:
        return jsonset(content={'error': 'неверная сложность задания'}, status_code=400)
    try:
        task = await coursesDB.create_Test(
            _id=task_id,
            title=data.title.strip(),
            lesson_id=lesson_id,
            mode=mode,
            settings=data.settings,
            task_type=task_type,
            difficulty=data.difficulty,
            hint_mode=data.hint_mode,
            hint_text=data.hint_text,
        )
    except ValueError as exc:
        return jsonset(content={'error': str(exc)}, status_code=409)
    return jsonset(content=task, status_code=201)


@crouter.post('/check_answer')
async def main_answerCheck(data: dict, user=Depends(get_current_user)):
    task_instance_id = data.get('task_id')
    sol = await coursesDB.search_test__id(task_instance_id)
    if not sol:
        return jsonset(content={'error': 'задача не найдена'}, status_code=404)
    if sol.get('owner_uid') != user['user_uid']:
        return jsonset(content={'error': 'задача не найдена'}, status_code=404)
    # считаем по определению задачи, а не по сгенерированному варианту
    key = str(sol.get('parent_task_id') or task_instance_id)
    if not await coursesDB.course_for_task(user, str(key)):
        raise HTTPException(404, 'task not found')
    task_def = await coursesDB.search_tasks__id(_id=key)
    if not task_def:
        return jsonset(content={'error': 'задача не найдена'}, status_code=404)
    one_variant = _one_variant_per_student(task_def)
    if one_variant and key in await coursesDB.solved_task_ids(user['user_uid']):
        return jsonset(content={
            'error': 'назначенный вариант уже решён',
            'completed': True,
            'one_variant_per_student': True,
        }, status_code=409)
    max_wrong = _max_wrong_attempts(task_def)
    wrong_count = await coursesDB.wrong_attempts(user['user_uid'], key)
    if max_wrong and wrong_count >= max_wrong:
        return jsonset(content={
            'error': 'лимит неправильных ответов исчерпан',
            'attempts': wrong_count,
            'max_wrong_attempts': max_wrong,
            'attempts_remaining': 0,
            'locked': True,
        }, status_code=409)
    # подсказка не блокирует, но очков за задание больше не даёт
    hinted = key in await coursesDB.hinted_task_ids(user['user_uid'])
    # тип задания берем из варианта, а если его нет (старые записи) — из определения
    task_type = sol.get('task_type')
    if task_type is None:
        task_type = task_def.get('type')
    sub = await _validate_submission(task_type, data['user_input'], sol['internal_solution'])
    if sub.get('is_correct'):
        if hinted:
            # решено с подсказкой: это НЕ самостоятельное решение —
            # очков нет, в прогресс «решено» задача не попадает
            sub['hint_used'] = True
            sub['rating_awarded'] = 0
            sub['solve_count'] = await coursesDB.task_solves(user['user_uid'], key)
            sub['next_reward'] = 0
        else:
            # задание бесконечное: награда растет с каждым решением до 1000
            base = sub.get('score') or coursesDB.BASE_TASK_REWARD
            reward, solves = await coursesDB.mark_task_solved(user['user_uid'], key, base)
            sub['rating_awarded'] = reward
            sub['solve_count'] = solves
            sub['next_reward'] = coursesDB.reward_for(
                coursesDB.BASE_TASK_REWARD, solves)
            await usersDB.add_rating(user['user_uid'], reward)
        # этот вариант отработан — в следующий раз сгенерируем новое задание
        await coursesDB.drop_tests_for(key, user['user_uid'])
    else:
        registered = await coursesDB.register_wrong_attempt(
            user['user_uid'], key, max_wrong,
        )
        if registered is None:
            registered = await coursesDB.wrong_attempts(user['user_uid'], key)
        wrong_count = registered
    sub['attempts'] = wrong_count
    sub['max_wrong_attempts'] = max_wrong
    sub['attempts_remaining'] = max(0, max_wrong - wrong_count) if max_wrong else None
    sub['locked'] = bool(max_wrong and wrong_count >= max_wrong and not sub.get('is_correct'))
    sub['one_variant_per_student'] = one_variant
    sub['completed'] = bool(one_variant and sub.get('is_correct'))
    return jsonset(content=sub, status_code=200)


@crouter.get('/getTest/{click_from}')
async def main_taskGetter(click_from: str, user=Depends(get_current_user)):
    if (tmp := await coursesDB.search_tasks__id(_id=click_from)):
        if not await coursesDB.course_for_task(user, click_from):
            raise HTTPException(404, 'task not found')
        # задания идут по порядку: сначала закрываем предыдущие в этом уроке
        solved = await coursesDB.solved_task_ids(user['user_uid'])
        hinted = await coursesDB.hinted_task_ids(user['user_uid'])
        closed = solved | hinted  # подсказка тоже разблокирует следующие задания
        already = str(tmp['_id']) in solved
        hint_used = str(tmp['_id']) in hinted
        if not already:
            for t in await coursesDB.tasks_in_lesson(tmp['lesson_id']):
                if t['_id'] == tmp['_id']:
                    break  # дошли до текущего — все предыдущие закрыты
                if str(t['_id']) not in closed:
                    return jsonset(content={
                        'error': 'сначала реши предыдущие задания этого урока'
                    }, status_code=403)
        # вариант держим 30 минут: меньше мусора в базе и стабильные очки
        cached = await coursesDB.recent_test(click_from, user['user_uid'], minutes=30)
        if cached is None:
            variant_key = f"{user['user_uid']}:{click_from}" if _one_variant_per_student(tmp) else None
            cached = await _generate_variant(tmp, variant_key=variant_key)
            cached['parent_task_id'] = str(click_from)
            cached['owner_uid'] = user['user_uid']
            cached['task_type'] = tmp.get('type')
            await coursesDB.create_test(cached)
        solves = await coursesDB.task_solves(user['user_uid'], str(click_from))
        wrong_count = await coursesDB.wrong_attempts(user['user_uid'], str(click_from))
        max_wrong = _max_wrong_attempts(tmp)
        one_variant = _one_variant_per_student(tmp)
        # наружу отдаём без ответа и служебных полей
        return jsonset(content={
            'mode': cached.get('mode'),
            'task_id': cached.get('task_id'),
            'task_type': cached.get('task_type') or tmp.get('type'),
            'condition': cached.get('condition', {}),
            'tryings': wrong_count,
            'max_wrong_attempts': max_wrong,
            'attempts_remaining': max(0, max_wrong - wrong_count) if max_wrong else None,
            'locked': bool(max_wrong and wrong_count >= max_wrong),
            'one_variant_per_student': one_variant,
            'completed': bool(one_variant and already),
            'solved': already,
            'solves': solves,
            'next_reward': coursesDB.reward_for(coursesDB.BASE_TASK_REWARD, solves),
            'hint_used': hint_used,
            'hint_available': (tmp.get('hint_mode') or 'solution') != 'none',
            'hint_mode': tmp.get('hint_mode') or 'solution',
        }, status_code=200)
    return jsonset(
        content={
            'error': 'такого урока не существует'
        }, status_code=404
    )


@crouter.get('/solve_task/{task_id}')
async def main_taskSolver(task_id: str, user=Depends(get_current_user)):
    # подсказка показывает ответ, задание остается доступным для решения
    try:
        tid = int(task_id)  # task_id в базе int, строка не сматчилась бы
    except ValueError:
        return jsonset(content={'error': 'неверный id задачи'}, status_code=400)
    inst = await coursesDB.search_test__id(tid)
    key = (inst or {}).get('parent_task_id') or str(task_id)
    task = await coursesDB.search_tasks__id(_id=str(key))
    if not task or not await coursesDB.course_for_task(user, str(key)):
        return jsonset(content={'error': 'задача не найдена'}, status_code=404)
    hint_mode = task.get('hint_mode') or 'solution'
    if hint_mode == 'none':
        return jsonset(content={'error': 'подсказки для этой задачи отключены'}, status_code=404)
    if key in await coursesDB.solved_task_ids(user['user_uid']):
        return jsonset(content={'error': 'задача уже решена, подсказка не нужна'}, status_code=409)
    if hint_mode == 'text':
        text = (task.get('hint_text') or '').strip()
        if not text:
            return jsonset(content={'error': 'подсказка не задана'}, status_code=404)
        await coursesDB.mark_task_hint(user['user_uid'], key)
        return jsonset(content={'solution': text, 'hint_used': True, 'kind': 'hint'}, status_code=200)
    sol = (inst or {}).get('internal_solution') or {}
    if not sol:
        sol = (task or {}).get('internal_solution') or {}
    if sol.get('kind') == 'quiz':
        answer_map = {str(answer.get('id')): str(answer.get('text', ''))
                      for answer in (inst or {}).get('condition', {}).get('answers', [])}
        display = ', '.join(answer_map.get(str(answer_id), str(answer_id))
                            for answer_id in sol.get('correct', []))
        await coursesDB.mark_task_hint(user['user_uid'], key)
        return jsonset(content={'solution': display, 'hint_used': True, 'kind': 'solution'}, status_code=200)
    canonical = sol.get('canonical_5_3') or sol.get('canonical')
    if canonical is None:
        return jsonset(content={'error': 'подсказки для этой задачи нет'}, status_code=404)
    # у математики ответ — просто число, у ДНК/РНК оборачиваем в 5'/3'
    if sol.get('kind') == 'math' or sol.get('type') == 'number':
        display = str(canonical)
    else:
        display = f"5'-{canonical}-3'"
    # фиксируем использование: очков за это задание больше не будет
    await coursesDB.mark_task_hint(user['user_uid'], key)
    return jsonset(content={'solution': display, 'hint_used': True}, status_code=200)


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
    if not await coursesDB.course_for_lesson(user, lesson_id):
        raise HTTPException(404, 'lesson not found')
    # урок прочитан: фронт зовет, когда долистал контент до конца
    fresh = await coursesDB.mark_lesson_read(user['user_uid'], lesson_id)
    return jsonset(content={'ok': True, 'fresh': fresh}, status_code=200)


@crouter.get('/me/reads/{course_id}')
async def main_readList(course_id: str, user=Depends(get_current_user)):
    if not await coursesDB.course_for_user(user, course_id):
        raise HTTPException(404, 'course not found')
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
        field = 'type' if k == 'type_task' else k
        fields[field] = v.strip() if isinstance(v, str) else v
    if any(fields.get(name) == '' for name in ('lesson_id', 'mode', 'type')):
        return jsonset(content={'error': 'урок, mode и тип не могут быть пустыми'}, status_code=400)
    if 'difficulty' in fields and fields['difficulty'] not in {'easy', 'hard'}:
        return jsonset(content={'error': 'неверная сложность задания'}, status_code=400)
    try:
        res = await coursesDB.update_task(task_id, fields)
    except ValueError as exc:
        return jsonset(content={'error': str(exc)}, status_code=409)
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


@crouter.get('/news')
async def main_newsList(limit: int = 50):
    # публичная лента: страницу новостей видно и без входа
    return jsonset(content=await newsDB.published_news(limit=limit), status_code=200)


@crouter.get('/news/{news_id}')
async def main_newsItem(news_id: str):
    doc = await newsDB.get_news(news_id, published_only=True)
    if doc is None or not doc.get('is_published'):
        return jsonset(content={'error': 'новость не найдена'}, status_code=404)
    return jsonset(content=doc, status_code=200)


@crouter.get('/support')
async def main_supportInfo():
    # контакты поддержки для профиля и настроек
    return jsonset(content=await platformDB.get_support(), status_code=200)


@crouter.get('/lastnews')
async def rtNews():
    # лента дашборда: отдаём опубликованные новости из базы,
    # а если новостей ещё нет — запасной статичный список (чтобы блок не пустовал)
    rows = await newsDB.published_news(limit=20)
    if rows:
        return [
            {
                'title': n.get('title', ''),
                'text': n.get('text', ''),
                'emoji': n.get('emoji', ''),
                'url': n.get('image', ''),
                'id': n.get('_id'),
                'created_at': n.get('created_at'),
            }
            for n in rows
        ]
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
