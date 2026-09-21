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
        # Даже у истёкшей сессии можно безопасно проверить подпись без exp.
        # Это нужно только чтобы заблокированный пользователь увидел экран
        # ограничения вместо обычной ошибки авторизации.
        expired_payload = await utils.decode_token(token, verify_exp=False)
        if not expired_payload or not expired_payload.get('user_uid'):
            raise HTTPException(401, 'Invalid token')
        expired_user = await usersDB.search_usersByID(expired_payload['user_uid'])
        if not expired_user or expired_user.get('status') is not False:
            raise HTTPException(401, 'Invalid token')
        blocked_token = await utils.create_access_token({
            'role': expired_payload.get('role', 'user'),
            'user_uid': expired_user['user_uid'],
            'blocked': True,
        }, expires=False)
        raise HTTPException(
            403,
            detail={'code': 'account_blocked', 'reason': expired_user.get('blocked_reason', '')},
            headers={'X-Account-Blocked': '1', 'X-Blocked-Token': blocked_token},
        )

    user = await usersDB.search_usersByID(payload['user_uid'])
    if not user:
        raise HTTPException(401, 'User not found')
    if user.get('status') is False:
        blocked_token = await utils.create_access_token({
            'role': payload.get('role', 'user'),
            'user_uid': user['user_uid'],
            'blocked': True,
        }, expires=False)
        raise HTTPException(
            403,
            detail={'code': 'account_blocked', 'reason': user.get('blocked_reason', '')},
            headers={'X-Account-Blocked': '1', 'X-Blocked-Token': blocked_token},
        )
    user['role'] = payload['role']
    return user
