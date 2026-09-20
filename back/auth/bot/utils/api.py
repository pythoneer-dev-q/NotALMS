from back.server.database import usersDB, coursesDB

async def set_user_TG(user_id: int, username: str):
    return 'success' if await usersDB.settg(user_id, to_user=username) is True else 'false'

async def search_user(user_id: int):
    return await usersDB.search_usersByTelegram(user_id)

async def main_get_userAchievements(user_id: int) -> str:
    # раньше возвращался сырой документ юзера, теперь готовый текст
    user = await usersDB.search_usersByTelegram(user_id)
    if not user:
        return 'пользователь не найден, привяжи аккаунт через ссылку в профиле'
    ach = user.get('achivements') or []
    if not ach:
        return 'пока пусто, но всё впереди'
    return '\n'.join(f'• {k} — {v}' for item in ach for k, v in item.items())


async def main_get_userAchievementsRaw(user_id: int):
    # структура для клавиатуры: [(ключ, описание), ...]
    user = await usersDB.search_usersByTelegram(user_id)
    ach = (user or {}).get('achivements') or []
    return [(k, v) for item in ach for k, v in item.items()]


async def main_get_newsRaw():
    # сырые новости для клавиатуры
    from back.server.handlers.front_apiHandler import rtNews
    return await rtNews() or []

async def main_get_userCourses(user_id: int) -> str:
    # список курсов под роль user, готовый текст
    lst = await main_get_userCoursesRaw(user_id)
    if not lst:
        return 'пока нет доступных курсов'
    return '\n'.join(
        f'📌 <b>{c.get("title", "undefined")}</b> — {c.get("description") or "без описания"}'
        for c in lst
    )


async def main_get_userCoursesRaw(user_id: int):
    # сырой список для клавиатуры
    return await coursesDB.search_courses(role='user')


async def main_get_news() -> str:
    # новости платформы из бэка
    from back.server.handlers.front_apiHandler import rtNews
    items = await rtNews()
    if not items:
        return 'новостей пока нет'
    return '\n\n'.join(f'{i.get("emoji", "📰")} <b>{i["title"]}</b>\n{i.get("text", "")}' for i in items)


async def main_get_courseDescription(title: str) -> str:
    # описание курса по названию (для карточки в боте)
    lst = await coursesDB.search_courses(role='user')
    for c in lst:
        if c.get('title') == title:
            return c.get('description') or ''
    return ''


async def set_user_color(user_id: int, color: str) -> bool:
    # кастомизация цвета имени прямо из бота
    user = await usersDB.search_usersByTelegram(user_id)
    if not user:
        return False
    await usersDB.set_name_color(user['user_uid'], color)
    return True


async def get_user_color(user_id: int) -> str | None:
    user = await usersDB.search_usersByTelegram(user_id)
    return (user or {}).get('name_color')


async def unbind_user(user_id: int) -> bool:
    # отвязка аккаунта от телеграма
    user = await usersDB.search_usersByTelegram(user_id)
    if not user:
        return False
    await usersDB.unsettg(user_id)
    return True
