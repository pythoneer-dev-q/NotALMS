from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, HTTPException
from back.server.database import utils, usersDB

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    payload = await utils.decode_token(token)
    if not payload:
        raise HTTPException(401, 'Invalid token')

    user = await usersDB.search_usersByID(payload['user_uid'])
    if not user:
        raise HTTPException(401, 'User not found')
    user['role'] = payload['role']
    return user
