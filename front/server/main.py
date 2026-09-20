# ! front/server/main.py
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
from front.server import frontRouter
from back.server.server_configs.settings import settings

app = FastAPI()

app.include_router(frontRouter.frouter)
# статика ассетов: include_router не переносит Mount с роутера, вешаем на app
app.mount('/assets', StaticFiles(directory=frontRouter.ASSETS_DIR), name='assets')

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == '__main__':
    # ssl из env, если задан, иначе http
    ssl = {}
    if settings.ssl_certfile and settings.ssl_keyfile:
        ssl = dict(ssl_certfile=settings.ssl_certfile, ssl_keyfile=settings.ssl_keyfile)
    uvicorn.run(
        'front.server.main:app',
        host=settings.front_host,
        port=settings.front_port,
        workers=settings.workers,
        **ssl,
    )