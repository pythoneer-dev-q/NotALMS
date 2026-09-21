# back/server/handlers/apihandler_conf/models.py
from pydantic import BaseModel

class Login(BaseModel):
    user_login: str
    user_password: str
    captcha_token: str | None = None

class Register(BaseModel):
    user_login: str
    user_password: str
    user_telegram_id: int | None = None    # только если галочка
    about_user: str | None = None          # фронт шлет null, если поле пустое
    captcha_token: str | None = None
    accepted_legal: bool = False
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
    reason: str | None = None


class AdminUserUpdate(BaseModel):
    user_login: str | None = None
    biography: str | None = None
    name_color: str | None = None
    hide_leaderboard: bool | None = None
    verified: bool | None = None


class UserVerify(BaseModel):
    user_uid: str
    verified: bool  # True — профиль проверен, False — снять галочку


class UserDelete(BaseModel):
    user_uid: str


class Biography(BaseModel):
    biography: str = ''  # «о себе»


class LeaderboardVisibility(BaseModel):
    hidden: bool  # True — скрыть себя из публичного рейтинга


class UsernameChange(BaseModel):
    user_login: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str
