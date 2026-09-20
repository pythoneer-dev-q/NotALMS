# back/server/handlers/apihandler_conf/models.py
from pydantic import BaseModel

class Login(BaseModel):
    user_login: str
    user_password: str

class Register(BaseModel):
    user_login: str
    user_password: str
    user_telegram_id: int | None = None    # только если галочка
    about_user: str | None = None          # фронт шлет null, если поле пустое
class GetSession(BaseModel):
    year_token: str

class TelegramLogin(BaseModel):
    code: str  # код из бота (/login)

class AdminCheck(BaseModel):
    secret: str  # пароль админки из env

class NameColor(BaseModel):
    color: str  # цвет имени, только из палитры

class Theme(BaseModel):
    name: str  # тема сайта, из списка THEMES


class UserSearch(BaseModel):
    q: str  # поиск по логину / uid


class UserSetStatus(BaseModel):
    user_uid: str
    status: str  # 'active' | 'blocked'


class UsernameChange(BaseModel):
    user_login: str