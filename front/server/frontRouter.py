# front/server/frontRouter.py
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

frouter = APIRouter()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "../assets/static")


@frouter.get('/index.html', response_class=HTMLResponse)
@frouter.get("/", response_class=HTMLResponse)
async def index():
    return open(f"{STATIC_DIR}/index.html", encoding='utf-8').read()


@frouter.get('/dash', response_class=HTMLResponse)
@frouter.get('/dash.html', response_class=HTMLResponse)
async def dash():
    return open(f'{STATIC_DIR}/dash.html', encoding='utf-8').read()


@frouter.get('/profile', response_class=HTMLResponse)
@frouter.get('/profile.html', response_class=HTMLResponse)
async def profile():
    return open(f'{STATIC_DIR}/profile.html', encoding='utf-8').read()

@frouter.get('/course/{courseId}', response_class=HTMLResponse)
@frouter.get('/course.html/{courseId}', response_class=HTMLResponse)
async def profile():
    return open(f'{STATIC_DIR}/course.html', encoding='utf-8').read()