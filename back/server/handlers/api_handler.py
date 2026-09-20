# ! back/server/handlers/api_handler.py
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Header, Depends
from pymongo.errors import DuplicateKeyError
from back.server.handlers.httpbearer import get_current_user
from fastapi.responses import HTMLResponse as htmlset, JSONResponse as jsonset
from back.server.handlers.apihandler_conf import models
from back.server.database import usersDB, utils, coursesDB
from back.server.handlers.front_apiHandler import rtNews, require_admin
from back.auth.bot import main
from back.auth.bot.databaseAuth import database as botdb
from back.server.server_configs.settings import settings
arouter = APIRouter(
    tags=["backend-api", "bugs-api"], prefix='/v1'
)

@arouter.post('/register')
async def main_registerReturnToken(data: models.Register):
    login = (data.user_login or '').strip()
    if not login or len(login) < 3 or len(login) > 32:
        return jsonset(content={'error': 'логин должен быть от 3 до 32 символов'}, status_code=400)
    pwd_error = utils.password_error(data.user_password)
    if pwd_error:
        return jsonset(content={'error': pwd_error}, status_code=400)
    if await usersDB.search_users(login) is not None:
        return jsonset(content={'error': 'такой логин уже занят', 'exists': True}, status_code=409)
    try:
        result = await usersDB.register_user(
            user_login=login,
            user_password=data.user_password,
            user_telegram_FOR_ANNOUCMENTS=data.user_telegram_id,
            about_user=data.about_user
        )
    except DuplicateKeyError:
        # успели зарегистрировать параллельно
        return jsonset(content={'error': 'такой логин уже занят', 'exists': True}, status_code=409)
    # пароль-хэш наружу не отдаем
    result.pop('hashed_password', None)
    result['JWTSession'] = await utils.create_access_token(
        data={
            'role': 'user',
            'user_uid': result.get('user_uid', '#none')
        }
    )
    return jsonset(
        content=result, status_code=200
    )


@arouter.post('/login')
async def main_loginReturnToken(data: models.Login):  
    user = await usersDB.search_users(data.user_login)
    if user and await utils.verify_password(data.user_password, user['hashed_password']):
        # заблокированного юзера не пускаем
        if user.get('status') is False:
            return jsonset(content={'error': 'аккаунт заблокирован'}, status_code=403)
        token = await utils.create_access_token({
            'role': 'user',
            'user_uid': user['user_uid']
        })
        return jsonset(content={'JWTSession': token}, status_code=200)
    
    return jsonset(content={'error': 'неверный логин или пароль'}, status_code=403)

def _username_cooldown(stamp, days: int = 3):
    # когда менялся логин и когда можно снова (iso-строки для фронта)
    if not stamp:
        return None, None
    if isinstance(stamp, str):
        stamp = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.isoformat(), (stamp + timedelta(days=days)).isoformat()


@arouter.get('/me')
async def me(user=Depends(get_current_user)):
    # фронту нужны рейтинг/цвет/тема — иначе шапка и статы пустые
    full = await usersDB.search_usersByID(user['user_uid']) or {}
    changed_at, next_change = _username_cooldown(full.get('last_username_change'))
    return {
        'user_login': user['user_login'],
        'user_uid': user['user_uid'],
        'role': user['role'],
        'rating': full.get('rating', 0),
        'name_color': full.get('name_color'),
        'theme': full.get('theme'),
        'status': full.get('status', True),
        'solved': await coursesDB.user_progress_count(user['user_uid']),
        'username_changed_at': changed_at,
        'username_next_change': next_change
    }


@arouter.get('/search_user')
async def search_user(user=Depends(get_current_user)):
    return await usersDB.search_usersByID(
        user_uid=user.get('user_uid', None)
    )
    
@arouter.get('/user_cabinet_bot_generateLink')
async def main_userBotCabinet(user=Depends(get_current_user)):
    user_telegram = await usersDB.search_users(user['user_login'])
    if not user_telegram.get('user_telegram_FOR_ANNOUCMENTS'):
        return jsonset(content={'is_registered': False,
                                'register_link': await main.main_GenerateLink(username=user['user_login'])})
    return jsonset(content={
        'is_registered': True
    })

@arouter.get('/check-login/{login}')
async def check_login(login: str):
    if not login:  # пустой логин
        return jsonset(
            content={"available": False, "message": "Логин не может быть пустым"},
            status_code=200
        )        
    existing = await usersDB.search_users(login)
    if existing:
        return jsonset(
            content={"available": False, "message": f"Логин {login} уже занят"},
            status_code=200
        )
    
    return jsonset(
        content={"available": True, "message": f"Отлично — {login} доступен вам!"},
        status_code=200
    )
    

@arouter.post(
    '/getData'
)
async def main_datagetterJWT(data: models.GetSession):
    if (tmp := utils.decode_token(
        data.year_token
    )) is not None:
        return jsonset(
            content=tmp, status_code=200
        )
    return jsonset(
        content={
            'error': 'доступ запрещен (неверный токен)'
        }, status_code=403
    )


@arouter.post('/login/telegram')
async def main_loginTelegram(data: models.TelegramLogin):
    # вход по одноразовому коду из бота (/login)
    code = data.code.strip()
    rec = await botdb.find_login_code(code)
    if not rec:
        return jsonset(content={'error': 'код не найден или истек'}, status_code=403)
    await botdb.drop_login_code(code)
    user = await usersDB.search_usersByTelegram(rec['login_user_id'])
    if not user:
        return jsonset(content={'error': 'аккаунт не привязан к telegram'}, status_code=403)
    # заблокированного юзера не пускаем и по тг
    if user.get('status') is False:
        return jsonset(content={'error': 'аккаунт заблокирован'}, status_code=403)
    token = await utils.create_access_token({
        'role': 'user',
        'user_uid': user['user_uid']
    })
    return jsonset(content={'JWTSession': token}, status_code=200)


@arouter.get('/rating/leaderboard')
async def main_leaderboard(user=Depends(get_current_user)):
    # топ-10 по очкам
    return jsonset(content=await usersDB.leaderboard(10), status_code=200)


@arouter.get('/me/progress')
async def main_myProgress(user=Depends(get_current_user)):
    prog = await coursesDB.user_progress(user['user_uid'])
    return jsonset(content={
        'solved': len(prog),
        'rating_position': await usersDB.rating_position(user['user_uid']),
        'items': prog
    }, status_code=200)


@arouter.get('/name-colors')
async def main_nameColors():
    # палитра для кастомизации имени
    return jsonset(content=usersDB.NAME_COLORS, status_code=200)


@arouter.get('/stats/public')
async def main_publicStats():
    # открытые цифры для главной страницы
    return jsonset(content={
        'courses': await coursesDB.courses.count_documents({}),
        'users': await usersDB.users.count_documents({})
    }, status_code=200)


@arouter.post('/me/name-color')
async def main_setNameColor(data: models.NameColor, user=Depends(get_current_user)):
    # только цвета из палитры, никаких инъекций стилей
    if data.color not in usersDB.NAME_COLORS:
        return jsonset(content={'error': 'такой цвет не разрешен'}, status_code=400)
    await usersDB.set_name_color(user['user_uid'], data.color)
    return jsonset(content={'ok': True, 'color': data.color}, status_code=200)


@arouter.get('/themes')
async def main_themes():
    # список тем сайта
    return jsonset(content=usersDB.THEMES, status_code=200)


@arouter.post('/me/theme')
async def main_setTheme(data: models.Theme, user=Depends(get_current_user)):
    # тема сохраняется в бд и применяется на всех страницах
    if data.name not in usersDB.THEMES:
        return jsonset(content={'error': 'неизвестная тема'}, status_code=400)
    await usersDB.set_theme(user['user_uid'], data.name)
    return jsonset(content={'ok': True, 'theme': data.name}, status_code=200)


@arouter.post('/me/telegram/unbind')
async def main_unbindTelegram(user=Depends(get_current_user)):
    # отвязка бота прямо из веба (кнопка «управление аккаунтом»)
    await usersDB.unsettg_by_uid(user['user_uid'])
    return jsonset(content={'ok': True}, status_code=200)


@arouter.put('/me/username')
async def main_changeUsername(data: models.UsernameChange, user=Depends(get_current_user)):
    # смена логина: не чаще раза в 3 дня
    if not data.user_login or len(data.user_login) < 3 or len(data.user_login) > 32:
        return jsonset(content={'error': 'логин 3–32 символа'}, status_code=400)
    res = await usersDB.change_username(user['user_uid'], data.user_login.strip())
    if 'error' in res:
        return jsonset(content=res, status_code=400)
    return jsonset(content=res, status_code=200)


@arouter.delete('/me/delete')
async def main_deleteUser(user=Depends(get_current_user)):
    # удаление аккаунта
    ok = await usersDB.delete_user(user['user_uid'])
    if ok:
        return jsonset(content={'ok': True}, status_code=200)
    return jsonset(content={'error': 'пользователь не найден'}, status_code=404)


@arouter.post('/admin/check')
async def main_adminCheck(data: models.AdminCheck):
    # сверка с ADMIN_SECRET из .env
    ok = bool(settings.admin_secret) and data.secret == settings.admin_secret
    return jsonset(content={'ok': ok}, status_code=200 if ok else 403)


@arouter.get('/admin/courses')
async def main_adminCourses(user=Depends(require_admin)):
    # все курсы, включая черновики; доступ по админ-секрету из env
    return await coursesDB.admin_all_courses()


@arouter.get('/admin/news')
async def main_adminNews(user=Depends(require_admin)):
    return jsonset(content=await rtNews(), status_code=200)


@arouter.get('/admin/users')
async def main_adminUsers(q: str = '', user=Depends(require_admin)):
    # список всех пользователей с поиском по логину / uid
    return await usersDB.admin_users(q=q)


@arouter.get('/admin/user/{user_uid}')
async def main_adminUserGet(user_uid: str, user=Depends(require_admin)):
    # карточка пользователя: прогресс, статус, привязка tg
    doc = await usersDB.admin_user_by_uid(user_uid)
    if not doc:
        return jsonset(content={'error': 'пользователь не найден'}, status_code=404)
    progress = await coursesDB.user_progress_count(user_uid)
    return jsonset(content={**doc, 'progress_count': progress}, status_code=200)


@arouter.post('/admin/user/status')
async def main_adminUserSetStatus(data: models.UserSetStatus, user=Depends(require_admin)):
    # блокировка / разблокировка пользователя
    await usersDB.admin_set_user_status(data.user_uid, data.status)
    return jsonset(content={'ok': True}, status_code=200)


        
        
