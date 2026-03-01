from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse as jsonset
from back.server.handlers.httpbearer import get_current_user
from back.server.database import coursesDB
from back.server.handlers.fronthandler_conf import models
from back.server.tasks import biologyUtil

crouter = APIRouter(prefix='/v1')


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
    print(courseData)
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
    '/createCourse'
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
    '/createLesson'
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
@crouter.post('/createTask')
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
async def main_answerCheck(data: dict):
    sol = await coursesDB.search_test__id(data['task_id'])
    print(sol)
    sub = await biologyUtil.validate_submission(user_input=data['user_input'], solution=sol['internal_solution'])
    return jsonset(content=sub, status_code=200)
@crouter.get('/getTest/{click_from}')
async def main_taskGetter(click_from: str):
    if (tmp := await coursesDB.search_tasks__id(_id=click_from)):
        user_task = await biologyUtil.generate_task(
            mode=int(tmp['mode']),
            length=int(tmp['settings']['taskLen'])
        )
        await coursesDB.create_test(user_task)
        user_task['_id'] = None
        return jsonset(content=user_task, status_code=200)
    return jsonset(
        content={
            'error': 'такого урока не существует'
        }, status_code=404
    )

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