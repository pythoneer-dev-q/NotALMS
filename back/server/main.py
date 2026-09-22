# ! back/server/main.py
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from back.server.handlers.api_handler import arouter
from back.server.handlers.front_apiHandler import crouter
from back.server.handlers.teacher_handler import router as teacher_router
from back.server.handlers.ratelimit import RateLimitMiddleware
from back.server.database.db_init import ensure_indexes
from back.server.database.client import close_client
from back.server.database import hotcache
from back.auth.bot.databaseAuth import database as bot_database
from back.server.runtime import configure_logging, install_loop_exception_handler
from back.server.server_configs.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    install_loop_exception_handler()
    await ensure_indexes()
    try:
        yield
    finally:
        await hotcache.close()
        bot_database.close_client()
        close_client()

app = FastAPI(lifespan=lifespan)

app.include_router(arouter)
app.include_router(crouter)
app.include_router(teacher_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# лимит на login/register/check-login
app.add_middleware(RateLimitMiddleware)

if __name__ == '__main__':
    # ssl из env, если задан, иначе http
    ssl = {}
    if settings.ssl_certfile and settings.ssl_keyfile:
        ssl = dict(ssl_certfile=settings.ssl_certfile, ssl_keyfile=settings.ssl_keyfile)
    uvicorn.run(
        'back.server.main:app',
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        access_log=settings.logging_enabled and settings.access_log_enabled,
        log_level=settings.log_level if settings.logging_enabled else 'critical',
        **ssl,
    )
