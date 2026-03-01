# ! back/server/handlers/api_handler.py
from fastapi import APIRouter, Header, Depends
from back.server.handlers.httpbearer import get_current_user
from fastapi.responses import HTMLResponse as htmlset, JSONResponse as jsonset
from back.server.handlers.apihandler_conf import models
from back.server.database import usersDB, utils
from back.auth.bot import main
from back.auth.bot.databaseAuth import database
arouter = APIRouter(
    tags=["backend-api", "bugs-api"], prefix='/v1'
)

@arouter.post('/register')
async def main_registerReturnToken(data: models.Register):
    if (await usersDB.search_users(data.user_login) is None):
        result = await usersDB.register_user(
            user_login=data.user_login,
            user_password=data.user_password,
            user_telegram_FOR_ANNOUCMENTS=data.user_telegram_id,
            about_user=data.about_user
        )
        result['JWTSession'] = await utils.create_access_token(
            data={
                'role': 'user',
                'user_uid': result.get('user_uid', '#none')
            }
        )
        return jsonset(
            content=result, status_code=200
        )
    return jsonset(
        content={
            'error': 'такой логин уже занят'
        }, status_code=403
    )

@arouter.post('/login')
async def main_loginReturnToken(data: models.Login):  
    user = await usersDB.search_users(data.user_login)
    if user and await utils.verify_password(data.user_password, user['hashed_password']):
        token = await utils.create_access_token({
            'role': 'user',
            'user_uid': user['user_uid']
        })
        return jsonset(content={'JWTSession': token}, status_code=200)
    
    return jsonset(content={'error': 'неверный логин или пароль'}, status_code=403)

@arouter.get('/me')
async def me(user=Depends(get_current_user)):
    return {
        'user_login': user['user_login'],
        'user_uid': user['user_uid'],
        'role': user['role']
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

        
        
