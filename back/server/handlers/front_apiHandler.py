from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse as jsonset
from handlers.httpbearer import get_current_user
from database import coursesDB
from handlers.fronthandler_conf import models

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
async def main_lessonSearcher(course_id: str):
    lessonsData = await coursesDB.search_lessons(
        course_id=course_id
    )
    return jsonset(
        content=lessonsData, status_code=200)
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