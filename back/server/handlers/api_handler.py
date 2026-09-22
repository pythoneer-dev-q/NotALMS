# ! back/server/handlers/api_handler.py
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Header, Depends, Request
from pymongo.errors import DuplicateKeyError
from back.server.handlers.httpbearer import get_current_user
from fastapi.responses import HTMLResponse as htmlset, JSONResponse as jsonset
from back.server.handlers.apihandler_conf import models
from back.server.handlers.fronthandler_conf import models as front_models
from back.server.database import usersDB, utils, coursesDB, newsDB, platformDB
from back.server.handlers.front_apiHandler import require_admin
from back.auth.bot import main
from back.auth.bot.databaseAuth import database as botdb
from back.server.server_configs.settings import settings
from back.server.handlers import captcha
arouter = APIRouter(
    tags=["backend-api", "bugs-api"], prefix='/v1'
)

@arouter.post('/register')
async def main_registerReturnToken(data: models.Register, request: Request):
    if not data.accepted_legal:
        return jsonset(content={'error': 'нужно принять политику конфиденциальности и правила использования'}, status_code=400)
    if not await captcha.verify(data.captcha_token, request, 'register'):
        return jsonset(content={'code': 'captcha_required', 'error': 'подтвердите, что вы не робот'}, status_code=403)
    login = (data.user_login or '').strip()
    if not login or len(login) < 3 or len(login) > 32:
        return jsonset(content={'error': 'логин должен быть от 3 до 32 символов'}, status_code=400)
    pwd_error = utils.password_error(data.user_password)
    if pwd_error:
        return jsonset(content={'error': pwd_error}, status_code=400)
    if await usersDB.login_is_taken(login):
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
async def main_loginReturnToken(data: models.Login, request: Request):
    if not await captcha.verify(data.captcha_token, request, 'login'):
        return jsonset(content={'code': 'captcha_required', 'error': 'подтвердите, что вы не робот'}, status_code=403)
    user = await usersDB.search_users(data.user_login)
    if user and await utils.verify_password(data.user_password, user['hashed_password']):
        # Блокировка должна переживать обновление страницы: выдаем отдельный
        # бессрочный токен, но все защищенные API все равно отклонят его по status.
        account_type = user.get('account_type') or 'student'
        if user.get('status') is False:
            token = await utils.create_access_token({
                'role': 'teacher' if account_type == 'teacher' else 'user',
                'user_uid': user['user_uid'],
                'blocked': True,
            }, expires=False)
            return jsonset(
                content={'JWTSession': token, 'blocked': True}, status_code=200,
            )
        token = await utils.create_access_token({
            'role': 'teacher' if account_type == 'teacher' else 'user',
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
    stats = await coursesDB.user_stats(user['user_uid'])
    return {
        'user_login': user['user_login'],
        'user_uid': user['user_uid'],
        'role': user['role'],
        'account_type': user.get('account_type', 'student'),
        'rating': full.get('rating', 0),
        'name_color': full.get('name_color'),
        'theme': full.get('theme'),
        'status': full.get('status', True),
        'verified': bool(full.get('verified', False)),
        'hide_leaderboard': bool(full.get('hide_leaderboard', False)),
        'biography': full.get('biography'),
        'solved': stats['solved'],
        'hinted': stats['hinted'],
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
    login = (login or '').strip()
    if len(login) < 3 or len(login) > 32:
        return jsonset(
            content={"available": False, "message": "Логин должен быть от 3 до 32 символов"},
            status_code=200
        )        
    if await usersDB.login_is_taken(login):
        return jsonset(
            content={"available": False, "message": f"Логин {login} уже занят"},
            status_code=200
        )
    
    return jsonset(
        content={"available": True, "message": f"Отлично — {login} доступен вам!"},
        status_code=200
    )


@arouter.get('/captcha/config')
async def captcha_config():
    """Only the public site key can go to the browser; secret stays on backend."""
    return {
        'enabled': settings.turnstile_enabled,
        'sitekey': settings.turnstile_site_key if settings.turnstile_enabled else '',
    }


@arouter.put('/me/password')
async def change_password(data: models.PasswordChange, user=Depends(get_current_user)):
    if not await utils.verify_password(data.current_password, user.get('hashed_password', '')):
        return jsonset(content={'error': 'текущий пароль указан неверно'}, status_code=403)
    error = utils.password_error(data.new_password)
    if error:
        return jsonset(content={'error': error}, status_code=400)
    await usersDB.set_password(user['user_uid'], data.new_password)
    return jsonset(content={'ok': True}, status_code=200)
    

@arouter.post(
    '/getData'
)
async def main_datagetterJWT(data: models.GetSession):
    if (tmp := await utils.decode_token(
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
    # Для Telegram-входа действует тот же устойчивый сценарий блокировки.
    account_type = user.get('account_type') or 'student'
    if user.get('status') is False:
        token = await utils.create_access_token({
            'role': 'teacher' if account_type == 'teacher' else 'user',
            'user_uid': user['user_uid'],
            'blocked': True,
        }, expires=False)
        return jsonset(
            content={'JWTSession': token, 'blocked': True}, status_code=200,
        )
    token = await utils.create_access_token({
        'role': 'teacher' if account_type == 'teacher' else 'user',
        'user_uid': user['user_uid']
    })
    return jsonset(content={'JWTSession': token}, status_code=200)


@arouter.get('/rating/leaderboard')
async def main_leaderboard(limit: int = 10, user=Depends(get_current_user)):
    # топ-10 по очкам (старый формат — плоский список)
    return jsonset(content=await usersDB.leaderboard(limit=limit, include_hidden=False), status_code=200)


@arouter.get('/leaderboard')
async def main_leaderboardFull(
    limit: int = 20,
    skip: int = 0,
    q: str = '',
    verified_only: bool = False,
    x_admin_secret: str | None = Header(None),
    user=Depends(get_current_user),
):
    """Рейтинг с поиском и пагинацией.

    Обычные пользователи не видят скрытых (hide_leaderboard), админ — видит
    (передаёт x-admin-secret, как в админке).
    """
    include_hidden = bool(settings.admin_secret) and x_admin_secret == settings.admin_secret
    items = await usersDB.leaderboard(
        limit=limit, skip=skip, include_hidden=include_hidden, q=q, verified_only=verified_only
    )
    return jsonset(content={
        'items': items,
        'total': await usersDB.leaderboard_count(include_hidden=include_hidden, q=q, verified_only=verified_only),
        'include_hidden': include_hidden,
        'my_position': await usersDB.rating_position(user['user_uid'], include_hidden=include_hidden),
    }, status_code=200)


@arouter.get('/users/search')
async def main_usersSearch(q: str = '', limit: int = 20, user=Depends(get_current_user)):
    # поиск людей по логину (для страницы рейтинга/профилей)
    return jsonset(content=await usersDB.search_users_public(q, limit=limit), status_code=200)


@arouter.get('/users/{user_uid}')
async def main_userProfile(user_uid: str, user=Depends(get_current_user)):
    # открытый профиль пользователя: страница /user/{uid}
    doc = await usersDB.public_profile(user_uid)
    if doc is None:
        return jsonset(content={'error': 'пользователь не найден'}, status_code=404)
    solo = await coursesDB.user_progress_count(user_uid)
    doc['solved'] = solo
    try:
        doc['hinted'] = (await coursesDB.user_stats(user_uid))['hinted']
    except Exception:
        doc['hinted'] = 0
    return jsonset(content=doc, status_code=200)


@arouter.put('/me/biography')
async def main_setBiography(data: models.Biography, user=Depends(get_current_user)):
    # «о себе»: свободный текст, режем по длине на бэкенде
    text = (data.biography or '').strip()
    if len(text) > 1000:
        return jsonset(content={'error': 'максимум 1000 символов'}, status_code=400)
    await usersDB.set_biography(user['user_uid'], text)
    return jsonset(content={'ok': True, 'biography': text}, status_code=200)


@arouter.post('/me/leaderboard-visibility')
async def main_setVisibility(data: models.LeaderboardVisibility, user=Depends(get_current_user)):
    # скрыть/показать себя в рейтинге
    await usersDB.set_leaderboard_hidden(user['user_uid'], data.hidden)
    return jsonset(content={'ok': True, 'hidden': data.hidden}, status_code=200)


@arouter.get('/me/progress')
async def main_myProgress(user=Depends(get_current_user)):
    prog = await coursesDB.user_progress(user['user_uid'])
    stats = await coursesDB.user_stats(user['user_uid'])
    return jsonset(content={
        'solved': stats['solved'],
        'hinted': stats['hinted'],
        'closed': stats['closed'],
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
    # все новости, включая черновики
    return jsonset(content=await newsDB.all_news(), status_code=200)


@arouter.post('/admin/news')
async def main_adminNewsCreate(data: front_models.AdminNewsCreate, user=Depends(require_admin)):
    # создание новости (по умолчанию — черновик)
    if not (data.title or '').strip():
        return jsonset(content={'error': 'нужен заголовок'}, status_code=400)
    if data.id and await newsDB.get_news(data.id):
        return jsonset(content={'error': 'новость с таким id уже есть'}, status_code=409)
    doc = await newsDB.create_news(
        title=data.title.strip(),
        text=data.text or '',
        emoji=data.emoji or '',
        image=data.image or '',
        tags=data.tags or [],
        order=data.order,
        is_published=data.is_published,
        author=None,
        news_id=data.id,
    )
    return jsonset(content=doc, status_code=200)


@arouter.put('/admin/news/{news_id}')
async def main_adminNewsUpdate(news_id: str, data: front_models.AdminNewsUpdate, user=Depends(require_admin)):
    fields = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    res = await newsDB.update_news(news_id, fields)
    if res is None:
        return jsonset(content={'error': 'новость не найдена'}, status_code=404)
    return jsonset(content=res, status_code=200)


@arouter.delete('/admin/news/{news_id}')
async def main_adminNewsDelete(news_id: str, user=Depends(require_admin)):
    res = await newsDB.delete_news(news_id)
    if res is None:
        return jsonset(content={'error': 'новость не найдена'}, status_code=404)
    return jsonset(content={'ok': True}, status_code=200)


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
    stats = await coursesDB.user_stats(user_uid)
    return jsonset(content={
        **doc,
        'progress_count': stats['solved'],
        'hinted_count': stats['hinted'],
        'rank': await usersDB.rating_position(user_uid, include_hidden=True),
    }, status_code=200)


@arouter.post('/admin/user/status')
async def main_adminUserSetStatus(data: models.UserSetStatus, user=Depends(require_admin)):
    # блокировка / разблокировка пользователя
    if data.status not in {'active', 'blocked'}:
        return jsonset(content={'error': 'неизвестный статус'}, status_code=400)
    await usersDB.admin_set_user_status(data.user_uid, data.status, data.reason)
    return jsonset(content={'ok': True}, status_code=200)


@arouter.get('/admin/support')
async def main_adminSupport(user=Depends(require_admin)):
    return jsonset(content=await platformDB.get_support(), status_code=200)


@arouter.put('/admin/support')
async def main_adminSupportUpdate(data: front_models.AdminSupportUpdate, user=Depends(require_admin)):
    if data.telegram and not data.telegram.startswith(('https://t.me/', 'https://telegram.me/')):
        return jsonset(content={'error': 'укажи ссылку вида https://t.me/username'}, status_code=400)
    return jsonset(content=await platformDB.set_support(data.email, data.telegram), status_code=200)


@arouter.put('/admin/user/{user_uid}')
async def main_adminUserUpdate(user_uid: str, data: models.AdminUserUpdate, user=Depends(require_admin)):
    fields = data.model_dump(exclude_none=True)
    if 'user_login' in fields and not 3 <= len(fields['user_login'].strip()) <= 32:
        return jsonset(content={'error': 'логин должен быть от 3 до 32 символов'}, status_code=400)
    if 'name_color' in fields and fields['name_color'] not in usersDB.NAME_COLORS:
        return jsonset(content={'error': 'недопустимый цвет имени'}, status_code=400)
    ok = await usersDB.admin_update_user(user_uid, fields)
    if not ok:
        return jsonset(content={'error': 'пользователь не найден или логин занят'}, status_code=409)
    return jsonset(content={'ok': True}, status_code=200)


@arouter.post('/admin/user/verify')
async def main_adminUserVerify(data: models.UserVerify, user=Depends(require_admin)):
    # галочка «профиль проверен»
    await usersDB.admin_set_user_verified(data.user_uid, data.verified)
    return jsonset(content={'ok': True, 'verified': data.verified}, status_code=200)


@arouter.delete('/admin/user/{user_uid}')
async def main_adminUserDelete(user_uid: str, user=Depends(require_admin)):
    # полное удаление аккаунта вместе с прогрессом
    ok = await usersDB.admin_delete_user(user_uid)
    if not ok:
        return jsonset(content={'error': 'пользователь не найден'}, status_code=404)
    return jsonset(content={'ok': True}, status_code=200)


        
