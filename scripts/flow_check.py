# сквозной прогон задания: getTest -> check_answer -> повтор -> подсказка -> прогресс
# проверяет, что верный ответ не уходит на фронт и очки не дублируются
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import asyncio, json, random, re, urllib.request, urllib.error

BASE = 'http://127.0.0.1:8004'


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None


async def seed_task_def():
    # задание-определение, из него getTest делает вариант
    from back.server.database import coursesDB
    def_id = 'flowdef_' + str(random.randint(1000, 999999))
    await coursesDB.create_Test(
        _id=def_id, lesson_id='flowlesson', mode='1',
        settings={'taskLen': 12}, task_type='dna', difficulty='easy'
    )
    return def_id


def canonical_from(task):
    # ответ берём из базы (фронт его не видит) — как если бы школьник решил верно
    from pymongo import MongoClient
    from back.server.server_configs.settings import settings
    cli = MongoClient(settings.mongo_uri)
    db = cli[settings.mongo_lmscluster]
    doc = db[settings.mongo_lmstests].find_one({'task_id': task['task_id']})
    assert doc and doc.get('internal_solution'), ('нет internal_solution в базе', doc)
    sol = doc['internal_solution']
    # mongo хранит каноническую строку 5'->3' (кириллицей)
    return sol['canonical_5_3'] if isinstance(sol, dict) else sol


def main():
    def_id = asyncio.run(seed_task_def())
    login = 'flow_' + str(random.randint(10000, 99999))
    st, reg = call('POST', '/v1/register',
                   {'user_login': login, 'user_password': 'pw123456', 'about_user': None})
    assert st == 200, ('register', st)
    tok = reg['JWTSession']

    st, t1 = call('GET', f'/v1/getTest/{def_id}', token=tok)
    assert st == 200, ('getTest', st)
    assert 'internal_solution' not in t1, 'утечка ответа в getTest!'
    assert t1.get('condition', {}).get('top'), t1
    print('GETTEST OK task_id=', t1['task_id'], 'keys=', sorted(t1.keys()))

    st, t2 = call('GET', f'/v1/getTest/{def_id}', token=tok)
    assert t2['task_id'] == t1['task_id'], 'вариант пересоздается каждый раз'
    print('GETTEST_CACHED OK (тот же task_id)')

    answer = f"5'-{canonical_from(t1)}-3'"
    st, c1 = call('POST', '/v1/check_answer',
                  {'task_id': t1['task_id'], 'user_input': answer}, token=tok)
    assert st == 200 and c1.get('is_correct'), ('check', st, c1)
    print('CHECK_OK awarded=', c1.get('rating_awarded'))

    st, c2 = call('POST', '/v1/check_answer',
                  {'task_id': t1['task_id'], 'user_input': answer}, token=tok)
    assert c2.get('is_correct') and 'rating_awarded' not in c2, ('double award', c2)
    print('NO_DOUBLE_AWARD OK')

    st, hint = call('GET', f'/v1/solve_task/{t1["task_id"]}', token=tok)
    assert st == 200 and hint['solution'] == answer, ('hint', st, hint)
    print('HINT OK ->', hint['solution'])

    st, pr = call('GET', '/v1/me/progress', token=tok)
    assert st == 200 and pr.get('solved', 0) >= 1, ('progress', st, pr)
    st, me = call('GET', '/v1/me', token=tok)
    assert me.get('rating', 0) > 0, ('rating', me)
    print('PROGRESS OK solved=', pr['solved'], 'rating=', me['rating'])

    print('FLOW_ALL_OK')


if __name__ == '__main__':
    main()
