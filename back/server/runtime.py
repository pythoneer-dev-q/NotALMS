import asyncio
import logging
import time

from back.server.server_configs.settings import settings


_last_disconnect_log = 0.0


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    if not settings.logging_enabled:
        level = logging.CRITICAL
    logging.getLogger().setLevel(level)
    for name in ('uvicorn', 'uvicorn.error', 'uvicorn.access'):
        logging.getLogger(name).setLevel(level)
    if not settings.access_log_enabled:
        logging.getLogger('uvicorn.access').disabled = True


def _expected_disconnect(context: dict) -> bool:
    exc = context.get('exception')
    if isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
        return True
    text = ' '.join((
        str(context.get('message') or ''),
        repr(context.get('handle') or ''),
        str(exc or ''),
    ))
    return (
        '_SelectorSocketTransport._call_connection_lost' in text
        and isinstance(exc, AttributeError)
        and ('connection_lost' in text or "'NoneType'" in text)
    )


def install_loop_exception_handler() -> None:
    loop = asyncio.get_running_loop()
    previous = loop.get_exception_handler()

    def handler(current_loop, context):
        global _last_disconnect_log
        if _expected_disconnect(context):
            now = time.monotonic()
            interval = max(0, settings.disconnect_log_interval_seconds)
            if settings.logging_enabled and now - _last_disconnect_log >= interval:
                _last_disconnect_log = now
                logger = logging.getLogger('notalms.network')
                method = getattr(logger, settings.expected_disconnect_log_level.lower(), logger.debug)
                method('Клиент разорвал сетевое соединение')
            return
        if previous:
            previous(current_loop, context)
        else:
            current_loop.default_exception_handler(context)

    loop.set_exception_handler(handler)
