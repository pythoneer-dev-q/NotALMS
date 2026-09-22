# ! back/server/database/utils.py
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
import hashlib
from back.server.server_configs.settings import settings

# из .env, а не из кода
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _normalize_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

async def hash_password(password: str) -> str:
    return pwd_context.hash(_normalize_password(password))

async def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_normalize_password(plain), hashed)

async def create_access_token(data: dict, expires: bool = True) -> str:
    to_encode = data.copy()
    if expires:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def decode_token(token: str, verify_exp: bool = True) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={'verify_exp': verify_exp},
        )
        # JWT is an identity envelope, not arbitrary client-controlled state.
        # Old or foreign tokens with extra claims must be rejected explicitly.
        allowed = {'user_uid', 'role', 'exp', 'blocked'}
        if set(payload) - allowed:
            return None
        if not isinstance(payload.get('user_uid'), str) or not payload['user_uid']:
            return None
        if payload.get('role') not in {'user', 'teacher'}:
            return None
        if payload.get('blocked') not in {None, True}:
            return None
        if payload.get('blocked') is True:
            if 'exp' in payload:
                return None
        elif 'exp' not in payload:
            return None
        return payload
    except JWTError:
        return None


# пароль: минимум 8 символов, строчная + заглавная + спецсимвол
PASSWORD_RULES = [
    ('минимум 8 символов', lambda p: len(p) >= 8),
    ('нужна строчная буква', lambda p: any(c.islower() for c in p)),
    ('нужна заглавная буква', lambda p: any(c.isupper() for c in p)),
    ('нужен спецсимвол', lambda p: any(not c.isalnum() for c in p)),
]


def password_error(password: str) -> str | None:
    # None = пароль подходит, иначе текст первого невыполненного требования
    for msg, ok in PASSWORD_RULES:
        if not ok(password or ''):
            return 'пароль: ' + msg
    return None
