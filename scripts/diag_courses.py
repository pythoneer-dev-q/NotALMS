# проверка редактирования урока: embed-видео и контент-блоки
import json, urllib.request as u, time

B = 'http://127.0.0.1:8004/v1'
SECRET = None
for line in open('.env', encoding='utf-8'):
    if line.startswith('ADMIN_SECRET='):
        SECRET = line.split('=', 1)[1].strip()


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


AH = ('x-admin-secret', SECRET)
ts = int(time.time())
cid, lid = f'diagc_{ts}', f'diagl_{ts}'
call('POST', '/createCourse', {'id': cid, 'title': 'diag курс', 'lessons': [lid], 'granted_to': ['all'], 'tags': [], 'order': 1, 'cover': '', 'description': '', 'difficulty': 'easy', 'is_published': True}, h=AH)
call('POST', '/createLesson', {'id': lid, 'course_id': cid, 'title': 'diag урок', 'type': 'theory', 'order': 1, 'content': [{'type': 'text', 'value': 'старый текст'}]}, h=AH)

s, lessons = call('GET', f'/admin/course/{cid}/lessons', h=AH)
print('ADMIN_LESSONS', s, len(lessons) if isinstance(lessons, list) else lessons)

# то, что шлет редактор после разбора кода встраивания
new_content = [
    {'type': 'text', 'value': 'новый текст урока'},
    {'type': 'list', 'items': ['пункт 1', 'пункт 2']},
    {'type': 'video', 'embed': 'https://www.youtube.com/embed/dQw4w9WgXcQ', 'embed_type': 'iframe'},
    {'type': 'video', 'embed': 'https://vk.com/js/api/openapi.js', 'embed_type': 'script'},
    {'type': 'video', 'url': 'https://rutube.ru/video/abc123/'},
]
s, r = call('PUT', f'/admin/lesson/{lid}', {'title': 'diag урок v2', 'order': 2, 'content': new_content}, h=AH)
print('LESSON_PUT', s)

s, lessons = call('GET', f'/admin/course/{cid}/lessons', h=AH)
l = lessons[0] if isinstance(lessons, list) and lessons else {}
print('LESSON_AFTER', s, l.get('title'), [b.get('type') for b in (l.get('content') or [])])
print('EMBED_IFRAME', (l.get('content') or [{}])[2])
print('BLOCKS_OK', l.get('content') == new_content)

print('DIAG_DONE')
