# проверка: тема переживает повторный вход по паролю
# (после логина /me должен отдавать выбранную тему, а не дефолт)
import json, random, urllib.request, urllib.error, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

BASE = 'http://127.0.0.1:8004/v1'


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {'Content-Type': 'application/json'}
    if token:
        h['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, None


login = 'theme_' + str(random.randint(10000, 99999))
pw = 'pw123456'

st, reg = call('POST', '/register', {'user_login': login, 'user_password': pw, 'about_user': None})
assert st == 200, ('register', st, reg)
tok = reg['JWTSession']

st, me = call('GET', '/me', token=tok)
print('FRESH_THEME', st, me.get('theme'))

st, r = call('POST', '/me/theme', {'name': 'ocean'}, token=tok)
assert st == 200 and r.get('theme') == 'ocean', ('set theme', st, r)
print('SET_THEME', st, r)

st, me = call('GET', '/me', token=tok)
print('ME_AFTER_SET', st, me.get('theme'))

# логин заново — тот же путь, что и кнопка "войти" на главной
st, lg = call('POST', '/login', {'user_login': login, 'user_password': pw})
assert st == 200 and lg.get('JWTSession'), ('login', st, lg)
tok2 = lg['JWTSession']

st, me2 = call('GET', '/me', token=tok2)
print('ME_AFTER_RELOGIN', st, me2.get('theme'))
st, su = call('GET', '/search_user', token=tok2)
print('SEARCH_USER_THEME', st, su.get('theme'))

ok = me2.get('theme') == 'ocean' and su.get('theme') == 'ocean'
print('THEME_PERSIST_OK' if ok else 'THEME_BUG_REPRODUCED')