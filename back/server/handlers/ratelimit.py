# ! back/server/handlers/ratelimit.py
# простой rate-limit без внешних либ, per-process (для Docker-инстансов хватает)
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from back.server.server_configs.settings import settings

# что лимитируем
LIMITED_PATHS = {'/v1/login', '/v1/register', '/v1/check-login'}

_WINDOWS = {'second': 1, 'minute': 60, 'hour': 3600}


def _parse(spec: str) -> tuple[int, int]:
    n, _, per = spec.partition('/')
    return int(n), _WINDOWS.get(per.strip(), 60)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.max, self.window = _parse(settings.rate_limit)
        self.hits: dict[str, list[float]] = {}
        self.second_hits: dict[str, list[float]] = {}

    async def dispatch(self, request, call_next):
        if request.url.path not in LIMITED_PATHS:
            return await call_next(request)
        ip = request.client.host if request.client else '?'
        now = time.monotonic()
        second_bucket = [t for t in self.second_hits.get(ip, []) if now - t < 1]
        second_bucket.append(now)
        self.second_hits[ip] = second_bucket
        if settings.turnstile_enabled and len(second_bucket) > settings.captcha_suspicious_rps:
            self.second_hits[ip] = []
            return JSONResponse(
                {'code': 'captcha_required', 'error': 'подтвердите, что вы не робот'},
                status_code=403,
                headers={'X-Captcha-Required': '1'},
            )
        bucket = [t for t in self.hits.get(ip, []) if now - t < self.window]
        if len(bucket) >= self.max:
            return JSONResponse(
                {'error': 'слишком много запросов, подожди немного'},
                status_code=429
            )
        bucket.append(now)
        self.hits[ip] = bucket
        # подрезаем карту, чтобы не текла
        if len(self.hits) > 10000:
            self.hits = {k: v for k, v in self.hits.items() if now - v[-1] < self.window}
        return await call_next(request)
