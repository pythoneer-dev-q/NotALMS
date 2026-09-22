from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from back.server.database import accessDB, coursesDB
from back.server.handlers.fronthandler_conf import models as course_models
from back.server.handlers.httpbearer import get_current_user
from back.server.server_configs.settings import settings


router = APIRouter(prefix='/v1')


class InviteCreate(BaseModel):
    hours: int = Field(default=24, ge=1, le=8760)
    max_uses: int = Field(default=1, ge=1, le=10000)


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default='', max_length=500)
    member_limit: int = Field(default=0, ge=0, le=10000)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    member_limit: int | None = Field(default=None, ge=0, le=10000)


def require_admin(x_admin_secret: str | None = Header(None)):
    if not settings.admin_secret or x_admin_secret != settings.admin_secret:
        raise HTTPException(403, 'admin secret invalid')


async def require_teacher(user=Depends(get_current_user)):
    if user.get('account_type') != 'teacher':
        raise HTTPException(403, 'teacher account required')
    return user


async def _owned_roles(user_uid: str, role_ids: list[str]) -> list[str]:
    unique = list(dict.fromkeys(role_ids or []))
    for role_id in unique:
        if not await accessDB.owned_role(user_uid, role_id):
            raise HTTPException(403, 'a study group does not belong to this teacher')
    return unique


@router.get('/invites/{token}')
async def invite_preview(token: str):
    doc = await accessDB.inspect_invite(token)
    if not doc:
        raise HTTPException(404, 'invite is invalid or expired')
    return doc


@router.post('/invites/{token}/claim')
async def invite_claim(token: str, user=Depends(get_current_user)):
    result = await accessDB.claim_invite(token, user['user_uid'])
    if result.get('error'):
        raise HTTPException(409, result['error'])
    result['account_type'] = await accessDB.account_type(user['user_uid'])
    return result


@router.post('/admin/teacher-invites', dependencies=[Depends(require_admin)])
async def admin_teacher_invite(data: InviteCreate):
    return await accessDB.create_invite('teacher', None, data.hours, max_uses=data.max_uses)


@router.get('/admin/teacher-invites', dependencies=[Depends(require_admin)])
async def admin_teacher_invites():
    return await accessDB.list_invites(kind='teacher')


@router.delete('/admin/teacher-invites/{invite_id}', dependencies=[Depends(require_admin)])
async def admin_revoke_teacher_invite(invite_id: str):
    if not await accessDB.revoke_invite(None, invite_id, admin=True):
        raise HTTPException(404, 'invite not found')
    return {'ok': True}


@router.get('/teacher/groups')
async def teacher_groups(user=Depends(require_teacher)):
    return await accessDB.teacher_roles(user['user_uid'])


@router.post('/teacher/groups')
async def teacher_group_create(data: RoleCreate, user=Depends(require_teacher)):
    return await accessDB.create_role(user['user_uid'], data.name, data.description, data.member_limit)


@router.put('/teacher/groups/{role_id}')
async def teacher_group_update(role_id: str, data: RoleUpdate, user=Depends(require_teacher)):
    doc = await accessDB.update_role(user['user_uid'], role_id, data.model_dump(exclude_none=True))
    if not doc:
        raise HTTPException(404, 'study group not found')
    return doc


@router.post('/teacher/groups/{role_id}/invites')
async def teacher_group_invite(role_id: str, data: InviteCreate, user=Depends(require_teacher)):
    if not await accessDB.owned_role(user['user_uid'], role_id):
        raise HTTPException(404, 'study group not found')
    return await accessDB.create_invite(
        'group', user['user_uid'], data.hours, role_id=role_id, max_uses=data.max_uses,
    )


@router.get('/teacher/invites')
async def teacher_invites(user=Depends(require_teacher)):
    return await accessDB.list_invites(owner_uid=user['user_uid'], kind='group')


@router.delete('/teacher/invites/{invite_id}')
async def teacher_revoke_invite(invite_id: str, user=Depends(require_teacher)):
    if not await accessDB.revoke_invite(user['user_uid'], invite_id):
        raise HTTPException(404, 'invite not found')
    return {'ok': True}


@router.get('/teacher/groups/{role_id}/students')
async def teacher_students(role_id: str, q: str = '', user=Depends(require_teacher)):
    rows = await accessDB.role_students(user['user_uid'], role_id, q)
    if rows is None:
        raise HTTPException(404, 'study group not found')
    return rows


@router.delete('/teacher/groups/{role_id}/students/{student_uid}')
async def teacher_remove_student(role_id: str, student_uid: str, user=Depends(require_teacher)):
    course_ids = await coursesDB.course_scope_ids(role_id, user['user_uid'])
    if not await accessDB.remove_membership(user['user_uid'], role_id, student_uid):
        raise HTTPException(404, 'student is not in this study group')
    await coursesDB.clear_user_course_progress(student_uid, course_ids)
    return {'ok': True}


@router.delete('/teacher/groups/{role_id}')
async def teacher_group_delete(role_id: str, user=Depends(require_teacher)):
    students = await accessDB.role_students(user['user_uid'], role_id, limit=10000) or []
    course_ids = await coursesDB.course_scope_ids(role_id, user['user_uid'])
    for student in students:
        await coursesDB.clear_user_course_progress(student['user_uid'], course_ids)
    if not await accessDB.archive_role(user['user_uid'], role_id):
        raise HTTPException(404, 'study group not found')
    return {'ok': True}


@router.get('/teacher/courses')
async def teacher_courses(user=Depends(require_teacher)):
    return await coursesDB.teacher_courses(user['user_uid'])


@router.post('/teacher/courses')
async def teacher_course_create(data: course_models.RegVisibleCourse, user=Depends(require_teacher)):
    role_ids = await _owned_roles(user['user_uid'], data.role_ids)
    if await coursesDB.search_course_admin(data.id):
        raise HTTPException(409, 'course id is already used')
    return await coursesDB.create_courseVisible(
        _id=data.id.strip(), title=data.title.strip(), lessons=[],
        granted_to=[], tags=data.tags, order=data.order, cover=data.cover,
        description=data.description, difficulty=data.difficulty,
        is_published=data.is_published, owner_uid=user['user_uid'], role_ids=role_ids,
    )


@router.get('/teacher/courses/{course_id}')
async def teacher_course_get(course_id: str, user=Depends(require_teacher)):
    doc = await coursesDB.course_for_user(user, course_id)
    if not doc:
        raise HTTPException(404, 'course not found')
    return doc


@router.put('/teacher/courses/{course_id}')
async def teacher_course_update(course_id: str, data: course_models.AdminCourseUpdate,
                                user=Depends(require_teacher)):
    if not await coursesDB.course_for_user(user, course_id):
        raise HTTPException(404, 'course not found')
    fields = data.model_dump(exclude_none=True)
    fields.pop('granted_to', None)
    fields.pop('lessons', None)
    if 'role_ids' in fields:
        fields['role_ids'] = await _owned_roles(user['user_uid'], fields['role_ids'])
    await coursesDB.update_course(course_id, fields)
    return {'ok': True}


@router.delete('/teacher/courses/{course_id}')
async def teacher_course_delete(course_id: str, user=Depends(require_teacher)):
    if not await coursesDB.course_for_user(user, course_id):
        raise HTTPException(404, 'course not found')
    await coursesDB.delete_course(course_id)
    return {'ok': True}


@router.get('/teacher/courses/{course_id}/lessons')
async def teacher_lessons(course_id: str, user=Depends(require_teacher)):
    if not await coursesDB.course_for_user(user, course_id):
        raise HTTPException(404, 'course not found')
    return await coursesDB.search_lessons(course_id)


@router.post('/teacher/lessons')
async def teacher_lesson_create(data: course_models.RegVisibleLesson, user=Depends(require_teacher)):
    if not await coursesDB.course_for_user(user, data.course_id):
        raise HTTPException(404, 'course not found')
    try:
        return await coursesDB.create_lessonIn(
            data.id.strip(), data.course_id, data.title.strip(), data.content, data.type, data.order,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.put('/teacher/lessons/{lesson_id}')
async def teacher_lesson_update(lesson_id: str, data: course_models.AdminLessonUpdate,
                                user=Depends(require_teacher)):
    if not await coursesDB.course_for_lesson(user, lesson_id):
        raise HTTPException(404, 'lesson not found')
    await coursesDB.update_lesson(lesson_id, data.model_dump(exclude_none=True))
    return {'ok': True}


@router.delete('/teacher/lessons/{lesson_id}')
async def teacher_lesson_delete(lesson_id: str, user=Depends(require_teacher)):
    if not await coursesDB.course_for_lesson(user, lesson_id):
        raise HTTPException(404, 'lesson not found')
    await coursesDB.delete_lesson(lesson_id)
    return {'ok': True}


@router.get('/teacher/lessons/{lesson_id}/tasks')
async def teacher_tasks(lesson_id: str, user=Depends(require_teacher)):
    if not await coursesDB.course_for_lesson(user, lesson_id):
        raise HTTPException(404, 'lesson not found')
    return await coursesDB.search_tasks(lesson_id)


@router.post('/teacher/tasks')
async def teacher_task_create(data: course_models.RegVisibleTask, user=Depends(require_teacher)):
    if not await coursesDB.course_for_lesson(user, data.lesson_id):
        raise HTTPException(404, 'lesson not found')
    if data.hint_mode not in {'none', 'text', 'solution'}:
        raise HTTPException(400, 'invalid hint mode')
    try:
        return await coursesDB.create_Test(
            data.id.strip(), data.lesson_id, data.mode.strip(), data.settings,
            data.title.strip(), data.type_task.strip(), data.difficulty,
            data.hint_mode, data.hint_text,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.put('/teacher/tasks/{task_id}')
async def teacher_task_update(task_id: str, data: course_models.AdminTaskUpdate,
                              user=Depends(require_teacher)):
    if not await coursesDB.course_for_task(user, task_id):
        raise HTTPException(404, 'task not found')
    raw = data.model_dump(exclude_none=True)
    if raw.get('hint_mode') not in {None, 'none', 'text', 'solution'}:
        raise HTTPException(400, 'invalid hint mode')
    if raw.get('lesson_id') and not await coursesDB.course_for_lesson(user, raw['lesson_id']):
        raise HTTPException(403, 'target lesson does not belong to this teacher')
    fields = {('type' if key == 'type_task' else key): value for key, value in raw.items()}
    await coursesDB.update_task(task_id, fields)
    return {'ok': True}


@router.delete('/teacher/tasks/{task_id}')
async def teacher_task_delete(task_id: str, user=Depends(require_teacher)):
    if not await coursesDB.course_for_task(user, task_id):
        raise HTTPException(404, 'task not found')
    await coursesDB.delete_task(task_id)
    return {'ok': True}


async def _role_task_ids(owner_uid: str, role_id: str) -> list[str]:
    return await coursesDB.task_ids_for_courses(await coursesDB.course_scope_ids(role_id, owner_uid))


@router.get('/teacher/groups/{role_id}/leaderboard')
async def teacher_leaderboard(role_id: str, user=Depends(require_teacher)):
    students = await accessDB.role_students(user['user_uid'], role_id, limit=10000)
    if students is None:
        raise HTTPException(404, 'study group not found')
    task_ids = await _role_task_ids(user['user_uid'], role_id)
    student_ids = [student['user_uid'] for student in students]
    progress_rows = await coursesDB.progress.find({
        'user_uid': {'$in': student_ids}, 'task_id': {'$in': task_ids},
    }).to_list(None) if task_ids and student_ids else []
    by_student: dict[str, list[dict]] = {}
    for row in progress_rows:
        by_student.setdefault(row['user_uid'], []).append(row)
    for student in students:
        rows = by_student.get(student['user_uid'], [])
        student['course_points'] = sum(coursesDB.total_points_for_row(row) for row in rows)
        student['solved'] = len(rows)
    students.sort(key=lambda row: (-row['course_points'], row.get('user_login', '').casefold()))
    for index, student in enumerate(students, 1):
        student['position'] = index
    return students


@router.get('/teacher/groups/{role_id}/students/{student_uid}/progress')
async def teacher_student_progress(role_id: str, student_uid: str, user=Depends(require_teacher)):
    students = await accessDB.role_students(user['user_uid'], role_id, student_uid)
    if students is None or not any(row['user_uid'] == student_uid for row in students):
        raise HTTPException(404, 'student not found')
    result = []
    for course_id in await coursesDB.course_scope_ids(role_id, user['user_uid']):
        course = await coursesDB.search_course_admin(course_id)
        lessons = await coursesDB.search_lessons(course_id)
        task_ids = await coursesDB.task_ids_for_courses([course_id])
        solved = await coursesDB.progress.find({
            'user_uid': student_uid, 'task_id': {'$in': task_ids},
        }, {'_id': 0}).to_list(None) if task_ids else []
        hinted = await coursesDB.hints.find({
            'user_uid': student_uid, 'task_id': {'$in': task_ids},
        }, {'_id': 0, 'task_id': 1}).to_list(None) if task_ids else []
        lesson_ids = [lesson['_id'] for lesson in lessons]
        task_docs = await coursesDB.tasks.find(
            {'lesson_id': {'$in': lesson_ids}}, {'_id': 1, 'title': 1, 'lesson_id': 1}
        ).to_list(None) if lesson_ids else []
        read = await coursesDB.reads.find({
            'user_uid': student_uid, 'lesson_id': {'$in': lesson_ids},
        }, {'_id': 0, 'lesson_id': 1}).to_list(None) if lesson_ids else []
        result.append({
            'course_id': course_id, 'title': course.get('title', course_id),
            'lessons_total': len(lessons), 'tasks_total': len(task_ids),
            'read_lessons': [row['lesson_id'] for row in read],
            'solved_tasks': solved,
            'hinted_tasks': [row['task_id'] for row in hinted],
            'lesson_details': [
                {'id': lesson['_id'], 'title': lesson.get('title', lesson['_id']),
                 'read': lesson['_id'] in {row['lesson_id'] for row in read}}
                for lesson in lessons
            ],
            'task_details': [
                {'id': str(task['_id']), 'title': task.get('title') or str(task['_id']),
                 'lesson_id': task.get('lesson_id'),
                 'status': ('solved' if str(task['_id']) in {str(row['task_id']) for row in solved}
                            else 'hinted' if str(task['_id']) in {str(row['task_id']) for row in hinted}
                            else 'unsolved')}
                for task in task_docs
            ],
        })
    return {'student': students[0], 'courses': result}
