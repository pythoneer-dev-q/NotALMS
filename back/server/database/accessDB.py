import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from back.server.database.client import get_db
from back.server.server_configs.settings import settings


database = get_db(settings.mongo_cluster)
roles = database[settings.mongo_study_roles]
memberships = database[settings.mongo_role_memberships]
invites = database[settings.mongo_role_invites]
users = database[settings.mongo_users]


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


async def ensure_indexes():
    await roles.create_index('owner_uid')
    await memberships.create_index([('role_id', 1), ('user_uid', 1)], unique=True)
    await memberships.create_index('user_uid')
    await invites.create_index('token_hash', unique=True)
    await invites.create_index('expires_at', expireAfterSeconds=0)
    await invites.create_index([('owner_uid', 1), ('kind', 1)])


async def account_type(user_uid: str) -> str:
    row = await users.find_one({'user_uid': user_uid}, {'account_type': 1})
    return (row or {}).get('account_type') or 'student'


async def create_invite(kind: str, owner_uid: str | None, hours: int,
                        role_id: str | None = None, max_uses: int = 1) -> dict:
    hours = max(1, min(int(hours), 24 * 365))
    max_uses = max(1, min(int(max_uses), 10000))
    raw = secrets.token_urlsafe(32)
    now = _now()
    doc = {
        '_id': str(uuid4()),
        'token_hash': _token_hash(raw),
        'kind': kind,
        'owner_uid': owner_uid,
        'role_id': role_id,
        'max_uses': max_uses,
        'uses': 0,
        'revoked': False,
        'created_at': now,
        'expires_at': now + timedelta(hours=hours),
    }
    await invites.insert_one(doc)
    return {**doc, 'token': raw, '_id': str(doc['_id'])}


async def inspect_invite(token: str) -> dict | None:
    doc = await invites.find_one({
        'token_hash': _token_hash(token),
        'revoked': False,
        'expires_at': {'$gt': _now()},
        '$expr': {'$lt': ['$uses', '$max_uses']},
    }, {'token_hash': 0})
    if doc and doc.get('role_id'):
        role = await roles.find_one({'_id': doc['role_id']}, {'name': 1, 'owner_uid': 1})
        if not role:
            return None
        doc['role_name'] = role.get('name', '')
    return doc


async def claim_invite(token: str, user_uid: str) -> dict:
    token_hash = _token_hash(token)
    preview = await inspect_invite(token)
    if not preview:
        return {'error': 'ссылка недействительна или срок истёк'}
    kind = preview.get('kind')
    if kind == 'group':
        if await account_type(user_uid) == 'teacher':
            return {'error': 'учитель не может вступить в учебную группу как ученик'}
        role = await roles.find_one({'_id': preview.get('role_id'), 'archived': {'$ne': True}})
        if not role:
            return {'error': 'учебная группа недоступна'}
        if await memberships.find_one({'role_id': role['_id'], 'user_uid': user_uid}):
            return {'ok': True, 'kind': 'group', 'role_id': role['_id'], 'already_member': True}
        limit = int(role.get('member_limit') or 0)
        if limit and await memberships.count_documents({'role_id': role['_id']}) >= limit:
            return {'error': 'в учебной группе закончились места'}

    claimed = await invites.find_one_and_update({
        'token_hash': token_hash,
        'revoked': False,
        'expires_at': {'$gt': _now()},
        '$expr': {'$lt': ['$uses', '$max_uses']},
    }, {'$inc': {'uses': 1}}, return_document=ReturnDocument.AFTER)
    if not claimed:
        return {'error': 'ссылка уже использована или срок истёк'}

    if kind == 'teacher':
        await users.update_one({'user_uid': user_uid}, {'$set': {'account_type': 'teacher'}})
        return {'ok': True, 'kind': 'teacher'}
    if kind == 'group':
        try:
            await memberships.insert_one({
                '_id': str(uuid4()),
                'role_id': claimed['role_id'],
                'user_uid': user_uid,
                'joined_at': _now(),
                'invite_id': str(claimed['_id']),
            })
        except DuplicateKeyError:
            pass
        return {'ok': True, 'kind': 'group', 'role_id': claimed['role_id']}
    return {'error': 'неизвестный тип приглашения'}


async def create_role(owner_uid: str, name: str, description: str = '', member_limit: int = 0) -> dict:
    doc = {
        '_id': str(uuid4()),
        'owner_uid': owner_uid,
        'name': name.strip()[:100],
        'description': description.strip()[:500],
        'member_limit': max(0, min(int(member_limit or 0), 10000)),
        'archived': False,
        'created_at': _now(),
    }
    await roles.insert_one(doc)
    return doc


async def teacher_roles(owner_uid: str) -> list[dict]:
    docs = await roles.find({'owner_uid': owner_uid, 'archived': {'$ne': True}}).sort('created_at', -1).to_list(None)
    for doc in docs:
        doc['members'] = await memberships.count_documents({'role_id': doc['_id']})
    return docs


async def owned_role(owner_uid: str, role_id: str) -> dict | None:
    return await roles.find_one({'_id': role_id, 'owner_uid': owner_uid, 'archived': {'$ne': True}})


async def user_role_ids(user_uid: str) -> list[str]:
    rows = await memberships.find({'user_uid': user_uid}, {'role_id': 1, '_id': 0}).to_list(None)
    return [row['role_id'] for row in rows]


async def role_students(owner_uid: str, role_id: str, q: str = '', limit: int = 100) -> list[dict] | None:
    if not await owned_role(owner_uid, role_id):
        return None
    ids = [row['user_uid'] for row in await memberships.find({'role_id': role_id}, {'user_uid': 1}).to_list(None)]
    if not ids:
        return []
    flt: dict = {'user_uid': {'$in': ids}}
    if q.strip():
        value = q.strip()
        flt['$or'] = [
            {'user_login': {'$regex': re.escape(value), '$options': 'i'}},
            {'user_uid': value},
        ]
    projection = {'_id': 0, 'hashed_password': 0, 'user_telegram_FOR_ANNOUCMENTS': 0, 'blocked_reason': 0}
    limit = max(1, min(int(limit), 10000))
    return await users.find(flt, projection).sort('rating', -1).limit(limit).to_list(limit)


async def revoke_invite(owner_uid: str | None, invite_id: str, admin: bool = False) -> bool:
    flt = {'_id': invite_id}
    if not admin:
        flt['owner_uid'] = owner_uid
    result = await invites.update_one(flt, {'$set': {'revoked': True}})
    return result.matched_count == 1


async def list_invites(owner_uid: str | None = None, kind: str | None = None) -> list[dict]:
    flt: dict = {}
    if owner_uid is not None:
        flt['owner_uid'] = owner_uid
    if kind:
        flt['kind'] = kind
    return await invites.find(flt, {'token_hash': 0}).sort('created_at', -1).limit(100).to_list(100)


async def update_role(owner_uid: str, role_id: str, fields: dict) -> dict | None:
    allowed = {key: value for key, value in fields.items() if key in {'name', 'description', 'member_limit'}}
    if 'name' in allowed:
        allowed['name'] = str(allowed['name']).strip()[:100]
    if 'description' in allowed:
        allowed['description'] = str(allowed['description']).strip()[:500]
    if 'member_limit' in allowed:
        allowed['member_limit'] = max(0, min(int(allowed['member_limit'] or 0), 10000))
    if not allowed:
        return None
    return await roles.find_one_and_update(
        {'_id': role_id, 'owner_uid': owner_uid, 'archived': {'$ne': True}},
        {'$set': allowed}, return_document=ReturnDocument.AFTER,
    )


async def remove_membership(owner_uid: str, role_id: str, user_uid: str) -> bool:
    if not await owned_role(owner_uid, role_id):
        return False
    result = await memberships.delete_one({'role_id': role_id, 'user_uid': user_uid})
    return result.deleted_count == 1


async def archive_role(owner_uid: str, role_id: str) -> bool:
    result = await roles.update_one(
        {'_id': role_id, 'owner_uid': owner_uid, 'archived': {'$ne': True}},
        {'$set': {'archived': True, 'archived_at': _now()}},
    )
    if result.modified_count:
        await memberships.delete_many({'role_id': role_id})
        await invites.update_many({'role_id': role_id}, {'$set': {'revoked': True}})
    return result.modified_count == 1


async def delete_user_access(user_uid: str):
    owned = [row['_id'] for row in await roles.find({'owner_uid': user_uid}, {'_id': 1}).to_list(None)]
    await memberships.delete_many({'$or': [{'user_uid': user_uid}, {'role_id': {'$in': owned}}]})
    await invites.delete_many({'$or': [{'owner_uid': user_uid}, {'role_id': {'$in': owned}}]})
    await roles.delete_many({'owner_uid': user_uid})
