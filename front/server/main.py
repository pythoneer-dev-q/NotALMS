import asyncio
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI 
import frontRouter

app = FastAPI()

app.include_router(frontRouter.frouter)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8005",
        "http://localhost:8005",
        "http://127.0.0.1:8004",
        "http://localhost:8004",
        "file://",
        "*",  
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8005)