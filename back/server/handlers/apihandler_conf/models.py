# back/server/handlers/apihandler_conf/models.py
from pydantic import BaseModel

class Login(BaseModel):
    user_login: str
    user_password: str

class Register(BaseModel):
    user_login: str
    user_password: str
    user_telegram_id: int | None = None    # только если галочка
    about_user: str = 'Расскажите о себе'
class GetSession(BaseModel):
    year_token: str