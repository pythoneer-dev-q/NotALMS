# ! back/server/database/newsDB.py
# новости платформы: отдельная коллекция, публикация/черновики, картинки
from uuid import uuid4
from datetime import datetime, timezone
from back.server.database.client import get_db
from back.server.database import hotcache
from back.server.server_configs.settings import settings

database = get_db(settings.mongo_lmscluster)
news = database[settings.mongo_lmsnews]

CACHE_PREFIX = 'news:list:'


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat(timespec='seconds', sep='T')


async def ensure_indexes():
    # быстрые выборки: лента опубликованных + сортировка
    await news.create_index('is_published')
    await news.create_index([('order', 1), ('created_at', -1)])


async def invalidate_news_cache():
    await hotcache.delete_prefix(CACHE_PREFIX)


def public_news(doc: dict) -> dict:
    # наружу отдаем только нужные поля, служебные не светим
    if not doc:
        return {}
    return {
        '_id': str(doc.get('_id', '')),
        'title': doc.get('title', ''),
        'text': doc.get('text', ''),
        'emoji': doc.get('emoji', ''),
        'image': doc.get('image', ''),
        'tags': doc.get('tags', []) or [],
        'order': doc.get('order', 0),
        'is_published': bool(doc.get('is_published', False)),
        'author': doc.get('author'),
        'created_at': doc.get('created_at'),
        'updated_at': doc.get('updated_at'),
    }


async def create_news(
    title: str,
    text: str = '',
    emoji: str = '',
    image: str = '',
    tags: list[str] | None = None,
    order: int = 0,
    is_published: bool = False,
    author: str | None = None,
    news_id: str | None = None,
) -> dict:
    now = _now()
    doc = {
        '_id': news_id or str(uuid4()),
        'title': title,
        'text': text,
        'emoji': emoji or '',
        'image': image or '',
        'tags': tags or [],
        'order': int(order or 0),
        'is_published': bool(is_published),
        'author': author,
        'created_at': now,
        'updated_at': now,
    }
    await news.insert_one(doc)
    await invalidate_news_cache()
    return public_news(doc)


async def update_news(news_id: str, fields: dict) -> dict | None:
    if not fields:
        return None
    fields['updated_at'] = _now()
    res = await news.find_one_and_update(
        {'_id': news_id}, {'$set': fields}, return_document=True
    )
    await invalidate_news_cache()
    if res is None:
        return None
    return public_news(res)


async def delete_news(news_id: str) -> dict | None:
    res = await news.find_one_and_delete({'_id': news_id})
    await invalidate_news_cache()
    if res is None:
        return None
    return public_news(res)


async def all_news() -> list[dict]:
    # для админки: и черновики, и опубликованные
    docs = await news.find({}).sort([('order', 1), ('created_at', -1)]).to_list(length=None)
    return [public_news(d) for d in docs]


async def published_news(limit: int | None = None) -> list[dict]:
    # лента: сначала кэш, чтобы не долбить базу на главной
    key = f'{CACHE_PREFIX}published'
    if settings.cache_ttl > 0:
        hit = await hotcache.get_json(key)
        if hit is not None:
            return hit[:limit] if limit else hit
    cur = news.find({'is_published': True}).sort([('order', 1), ('created_at', -1)])
    if limit:
        cur = cur.limit(limit)
    docs = await cur.to_list(length=None)
    result = [public_news(d) for d in docs]
    if settings.cache_ttl > 0:
        await hotcache.set_json(key, result, settings.cache_ttl)
    return result


async def get_news(news_id: str, published_only: bool = False) -> dict | None:
    query = {'_id': news_id}
    if published_only:
        query['is_published'] = True
    doc = await news.find_one(query)
    if doc is None:
        return None
    return public_news(doc)
