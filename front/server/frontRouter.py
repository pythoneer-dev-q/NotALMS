
# front/server/frontRouter.py
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, FileResponse
import os

frouter = APIRouter()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "../assets/static")
PAGES_DIR = os.path.join(os.path.dirname(__file__), '../assets/pages')
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "../assets")
# корень проекта: локально repo/, в docker /app (front/server -> x2 вверх)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
FAVICON = os.path.join(ROOT_DIR, 'favicon.ico')


def page(section: str, filename: str) -> str:
    with open(os.path.join(PAGES_DIR, section, filename), encoding='utf-8') as file:
        html = file.read()
    control_link = '<link rel="stylesheet" href="/assets/static/controls.css">'
    return html.replace('</head>', control_link + '</head>', 1)

# раньше функции дублировали имя profile — исправил


@frouter.get('/index.html', response_class=HTMLResponse)
@frouter.get("/", response_class=HTMLResponse)
async def index():
    return page('public', 'index.html')


@frouter.get('/dash', response_class=HTMLResponse)
@frouter.get('/dash.html', response_class=HTMLResponse)
async def dash():
    return page('account', 'dash.html')


@frouter.get('/profile', response_class=HTMLResponse)
@frouter.get('/profile.html', response_class=HTMLResponse)
async def profile():
    return page('account', 'profile.html')


@frouter.get('/course/{courseId}', response_class=HTMLResponse)
@frouter.get('/course.html/{courseId}', response_class=HTMLResponse)
async def coursePage(courseId: str):
    return page('course', 'course.html')


@frouter.get('/course/{courseId}/edit', response_class=HTMLResponse)
async def courseEditPage(courseId: str):
    # отдельная страница редактора курса для админов
    return page('course', 'edit_course.html')


@frouter.get('/adminSecret', response_class=HTMLResponse)
@frouter.get('/adminsecret.html', response_class=HTMLResponse)
async def adminPage():
    return page('admin', 'adminsecret.html')


@frouter.get('/login', response_class=HTMLResponse)
@frouter.get('/login.html', response_class=HTMLResponse)
async def login():
    # отдельной страницы нет, показываем index с открытой модалкой
    return page('public', 'index.html')


@frouter.get('/tg/{code}', response_class=HTMLResponse)
async def tgLogin(code: str):
    # диплинк из бота: авто-вход по одноразовому коду
    return page('public', 'tglogin.html')

@frouter.get('/settings', response_class=HTMLResponse)
async def settings():
    return page('account', 'settings.html')


@frouter.get('/blocked', response_class=HTMLResponse)
async def blocked():
    return page('public', 'blocked.html')


@frouter.get('/privacy', response_class=HTMLResponse)
async def privacy():
    return page('public', 'privacy.html')


@frouter.get('/terms', response_class=HTMLResponse)
async def terms():
    return page('public', 'terms.html')



# ===== новости =====
@frouter.get('/news', response_class=HTMLResponse)
@frouter.get('/news.html', response_class=HTMLResponse)
async def newsListPage():
    # отдельный пункт меню: лента опубликованных новостей
    return page('news', 'news.html')


@frouter.get('/news/edit', response_class=HTMLResponse)
async def newsCreatePage():
    # редактор новостей без id — создание новой
    return page('news', 'edit_news.html')


@frouter.get('/news/{news_id}/edit', response_class=HTMLResponse)
async def newsEditPage(news_id: str):
    # редактор конкретной новости (админ)
    return page('news', 'edit_news.html')


@frouter.get('/news/{news_id}', response_class=HTMLResponse)
async def newsItemPage(news_id: str):
    # страница отдельной новости с полным текстом
    return page('news', 'news_item.html')


@frouter.get('/users', response_class=HTMLResponse)
async def usersPage():
    return page('account', 'users.html')


# ===== открытый профиль пользователя =====
@frouter.get('/user/{user_uid}', response_class=HTMLResponse)
async def userPage(user_uid: str):
    # профиль любого участника по его уникальному id
    return page('account', 'user.html')


@frouter.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse(FAVICON, media_type='image/x-icon')
