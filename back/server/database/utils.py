# ! back/server/database/utils.py
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
import hashlib

SECRET_KEY = "твой_очень_длинный_секрет_1234567890abcde99999999"   # поменяй на свой (лучше 64+ символа)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES =  60 * 24 * 7  # 7 дней (можно 30 минут для теста)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _normalize_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

async def hash_password(password: str) -> str:
    return pwd_context.hash(_normalize_password(password))

async def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(_normalize_password(plain), hashed)

async def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None