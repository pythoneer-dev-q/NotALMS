# ! back/server/database/hotcache.py
# redis для горячих данных; redis недоступен — тихо работаем на памяти процесса
import json
import time
import redis.asyncio as aioredis
from back.server.server_configs.settings import settings

_redis = None
if settings.redis_url:
    _redis = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )

# фолбэк-память: key -> (expires_at, raw)
_mem: dict[str, tuple[float, str]] = {}


async def set_json(key: str, value, ttl: int = 60) -> None:
    raw = json.dumps(value, ensure_ascii=False, default=str)
    if _redis is not None:
        try:
            await _redis.set(key, raw, ex=ttl)
            return
        except Exception:
            pass  # redis умер, пишем в память
    now = time.monotonic()
    if len(_mem) >= 1000:
        expired = [cache_key for cache_key, item in _mem.items() if item[0] <= now]
        for cache_key in expired:
            _mem.pop(cache_key, None)
        if len(_mem) >= 1000:
            oldest = min(_mem, key=lambda cache_key: _mem[cache_key][0])
            _mem.pop(oldest, None)
    _mem[key] = (now + ttl, raw)


async def get_json(key: str):
    if _redis is not None:
        try:
            raw = await _redis.get(key)
            if raw is not None:
                return json.loads(raw)
        except Exception:
            pass
    hit = _mem.get(key)
    if hit and hit[0] > time.monotonic():
        return json.loads(hit[1])
    if hit:
        _mem.pop(key, None)
    return None


async def delete_prefix(prefix: str) -> None:
    # сброс по маске 'courses:list:*'
    if _redis is not None:
        try:
            keys = [k async for k in _redis.scan_iter(match=f'{prefix}*')]
            if keys:
                await _redis.delete(*keys)
        except Exception:
            pass
    for k in [k for k in _mem if k.startswith(prefix)]:
        _mem.pop(k, None)
