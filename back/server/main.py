# ! back/server/main.py
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from back.server.handlers.api_handler import arouter
from back.server.handlers.front_apiHandler import crouter
from back.server.handlers.ratelimit import RateLimitMiddleware
from back.server.database.db_init import ensure_indexes
from back.server.server_configs.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # индексы один раз на старте
    await ensure_indexes()
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(arouter)
app.include_router(crouter)
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
        **ssl,
    )