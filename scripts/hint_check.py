# фикс подсказки: кладем инстанс и проверяем solve_task по HTTP
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import asyncio, json, urllib.request

BASE = 'http://127.0.0.1:8004'

def post(path, body, headers=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', **(headers or {})})
    return json.loads(urllib.request.urlopen(req).read())

def get(path, headers):
    req = urllib.request.Request(BASE + path, headers=headers)
    return json.loads(urllib.request.urlopen(req).read())

async def seed():
    from back.server.tasks import biologyUtil
    from back.server.database import coursesDB
    t = await biologyUtil.generate_task(mode=1, length=12)
    await coursesDB.create_test(t)
    return t['task_id'], t['internal_solution']['canonical_5_3']

tid, canonical = asyncio.run(seed())
print('SEEDED task_id =', tid, 'canonical =', canonical)

login = 'hint_' + str(__import__('random').randint(10000, 99999))
reg = post('/v1/register', {'user_login': login, 'user_password': 'pw123456', 'about_user': None})
tok = reg['JWTSession']
sol = get(f'/v1/solve_task/{tid}', {'Authorization': f'Bearer {tok}'})
assert sol['solution'] == f"5'-{canonical}-3'", sol
print('SOLVE_TASK OK ->', sol['solution'])
