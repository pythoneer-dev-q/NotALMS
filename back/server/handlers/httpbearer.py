from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, HTTPException
from back.server.database import utils, usersDB

security = HTTPBearer()


def invalid_session():
    return HTTPException(
        401,
        detail={'code': 'invalid_session'},
        headers={'X-Session-Invalid': '1'},
    )

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
            raise invalid_session()
        expired_user = await usersDB.search_usersByID(expired_payload['user_uid'])
        if not expired_user or expired_user.get('status') is not False:
            raise invalid_session()
        account_type = expired_user.get('account_type') or 'student'
        blocked_token = await utils.create_access_token({
            'role': 'teacher' if account_type == 'teacher' else 'user',
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
        raise invalid_session()
    if payload.get('blocked') is True and user.get('status') is not False:
        # A permanent blocked-screen token is not a normal authenticated session.
        # Once the account is unblocked the user must sign in and receive a fresh token.
        raise invalid_session()
    if user.get('status') is False:
        account_type = user.get('account_type') or 'student'
        blocked_token = await utils.create_access_token({
            'role': 'teacher' if account_type == 'teacher' else 'user',
            'user_uid': user['user_uid'],
            'blocked': True,
        }, expires=False)
        raise HTTPException(
            403,
            detail={'code': 'account_blocked', 'reason': user.get('blocked_reason', '')},
            headers={'X-Account-Blocked': '1', 'X-Blocked-Token': blocked_token},
        )
    user['account_type'] = user.get('account_type') or 'student'
    user['role'] = 'teacher' if user['account_type'] == 'teacher' else 'user'
    return user
