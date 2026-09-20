# временный e2e: подсказка закрывает задание, админ-управление юзерами, урок прочитан
import json, urllib.request as u, time

B = 'http://127.0.0.1:8004/v1'
SECRET = None
for line in open('.env', encoding='utf-8'):
    if line.startswith('ADMIN_SECRET='):
        SECRET = line.split('=', 1)[1].strip()
assert SECRET, 'нет ADMIN_SECRET в .env'


def call(m, p, b=None, t=None, h=None):
    req = u.Request(B + p, method=m)
    req.add_header('content-type', 'application/json')
    if t: req.add_header('Authorization', 'Bearer ' + t)
    if h: req.add_header(*h)
    body = json.dumps(b).encode() if b is not None else None
    try:
        r = u.urlopen(req, body, timeout=10)
        return r.status, json.loads(r.read().decode() or '{}')
    except u.HTTPError as e:
        try: return e.code, json.loads(e.read().decode() or '{}')
        except Exception: return e.code, {}


login = 'e2e_user_' + str(int(time.time()))
pw = 'Passw0rd!'
s, r = call('POST', '/register', {'user_login': login, 'user_password': pw, 'about_user': None, 'user_telegram_id': None})
print('REGISTER', s)
tok = r.get('JWTSession')

# курс/урок/задание через админ-секрет
AH = ('x-admin-secret', SECRET)
cid = 'e2ecourse_' + str(int(time.time()))
lid = 'e2elesson_' + str(int(time.time()))
s, r = call('POST', '/createCourse', {'id': cid, 'title': 'e2e курс', 'lessons': [lid], 'granted_to': ['all'], 'tags': [], 'order': 1, 'cover': '', 'description': '', 'difficulty': 'easy', 'is_published': True}, h=AH)
print('COURSE', s)
s, r = call('POST', '/createLesson', {'id': lid, 'course_id': cid, 'title': 'урок 1', 'type': 'theory', 'order': 1, 'content': [{'type': 'text', 'value': 'текст урока'}]}, h=AH)
print('LESSON', s)
s, r = call('POST', '/createTask', {'id': 'e2etask_' + str(int(time.time())), 'lesson_id': lid, 'mode': '1', 'settings': {'taskLen': 6}, 'difficulty': 'easy', 'type_task': 'dna'}, h=AH)
print('TASK', s)

# урок прочитан
s, r = call('POST', f'/lesson/read/{lid}', {}, t=tok)
print('READ', s, r.get('fresh'))
s, r = call('GET', f'/me/reads/{cid}', t=tok)
print('READS', s, lid in (r.get('read') or []))

# открытие задания: сначала id задачи из урока
s, r = call('GET', f'/gettasks/{lid}', t=tok)
print('GETTASKS', s, len(r) if isinstance(r, list) else r)
task_def_id = r[0]['_id'] if isinstance(r, list) and r else None
s, r = call('GET', f'/getTest/{task_def_id}', t=tok)
print('GETTEST', s, 'hint_used' in r)
tid = r.get('task_id')

# подсказка
s, r = call('GET', f'/solve_task/{tid}', t=tok)
print('HINT', s, 'solution' in r, r.get('closed'))

# повторная подсказка — отклоняется
s, r = call('GET', f'/solve_task/{tid}', t=tok)
print('HINT_AGAIN', s)

# сдача после подсказки — закрыто
s, r = call('POST', '/check_answer', {'task_id': tid, 'user_input': "5'-AAAAAA-3'"}, t=tok)
print('CHECK_CLOSED', s, r.get('closed'), r.get('hint_used'))

# в me/solved задача в hinted, не в solved
s, r = call('GET', '/me/solved', t=tok)
print('SOLVED_LIST', s, 'hinted' in r and 'closed' in r)

# ===== админ-управление юзерами =====
s, r = call('GET', f'/admin/users?q={login}', h=AH)
print('ADMIN_USERS', s, isinstance(r, list) and len(r) >= 1)
uid = next((x['user_uid'] for x in r if isinstance(r, list) and x.get('user_login') == login), None)

s, r = call('GET', f'/admin/user/{uid}', h=AH)
print('ADMIN_USER_CARD', s, 'progress_count' in r, r.get('user_login') == login)

# блокируем и пробуем войти
s, r = call('POST', '/admin/user/status', {'user_uid': uid, 'status': 'blocked'}, h=AH)
print('BLOCK', s)
s, r = call('POST', '/login', {'user_login': login, 'user_password': pw})
print('LOGIN_BLOCKED', s, r.get('error'))
# разблокируем — снова пускает
s, r = call('POST', '/admin/user/status', {'user_uid': uid, 'status': 'active'}, h=AH)
s, r = call('POST', '/login', {'user_login': login, 'user_password': pw})
print('LOGIN_UNBLOCKED', s)

# без секрета админ-ручки закрыты
s, r = call('GET', '/admin/users')
print('ADMIN_NO_SECRET', s)

print('E2E_DONE')
