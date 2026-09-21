"""Server-side Cloudflare Turnstile validation for public auth forms."""
from uuid import uuid4
import httpx
from back.server.server_configs.settings import settings

VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'


def client_ip(request) -> str:
    forwarded = request.headers.get('cf-connecting-ip') or request.headers.get('x-forwarded-for', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.client.host if request.client else ''


async def verify(token: str | None, request, action: str) -> bool:
    """Validate a single-use Turnstile token. Disabled cleanly without keys."""
    if not settings.turnstile_enabled:
        return True
    if not token or len(token) > 2048:
        return False
    payload = {
        'secret': settings.turnstile_secret_key,
        'response': token,
        'remoteip': client_ip(request),
        'idempotency_key': str(uuid4()),
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(VERIFY_URL, data=payload)
            result = response.json()
        return bool(response.is_success and result.get('success') and result.get('action') == action)
    except (httpx.HTTPError, ValueError):
        return False
