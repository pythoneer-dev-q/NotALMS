import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from back.server.handlers.api_handler import arouter
from back.server.handlers.front_apiHandler import crouter

app = FastAPI()

app.include_router(arouter)
app.include_router(crouter)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8005",
        "http://localhost:8005",
        "http://127.0.0.1:8004",
        "http://localhost:8004",
        "file://",
        "*",  # ТОЛЬКО для разработки
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8004)