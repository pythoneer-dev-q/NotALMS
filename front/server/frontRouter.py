
# front/server/frontRouter.py
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, FileResponse
import os

frouter = APIRouter()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "../assets/static")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "../assets")
# корень проекта: локально repo/, в docker /app (front/server -> x2 вверх)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
FAVICON = os.path.join(ROOT_DIR, "favicon.ico")

# раньше функции дублировали имя profile — исправил


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
async def coursePage(courseId: str):
    return open(f'{STATIC_DIR}/course.html', encoding='utf-8').read()


@frouter.get('/course/{courseId}/edit', response_class=HTMLResponse)
async def courseEditPage(courseId: str):
    # отдельная страница редактора курса для админов
    return open(f'{STATIC_DIR}/edit_course.html', encoding='utf-8').read()


@frouter.get('/adminSecret', response_class=HTMLResponse)
@frouter.get('/adminsecret.html', response_class=HTMLResponse)
async def adminPage():
    return open(f'{STATIC_DIR}/adminsecret.html', encoding='utf-8').read()


@frouter.get('/login', response_class=HTMLResponse)
@frouter.get('/login.html', response_class=HTMLResponse)
async def login():
    # отдельной страницы нет, показываем index с открытой модалкой
    return open(f"{STATIC_DIR}/index.html", encoding='utf-8').read()


@frouter.get('/tg/{code}', response_class=HTMLResponse)
async def tgLogin(code: str):
    # диплинк из бота: авто-вход по одноразовому коду
    return open(f'{STATIC_DIR}/tglogin.html', encoding='utf-8').read()

@frouter.get('/settings', response_class=HTMLResponse)
async def settings():
    return open(f'{STATIC_DIR}/settings.html', encoding='utf-8').read()


@frouter.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse(FAVICON)
