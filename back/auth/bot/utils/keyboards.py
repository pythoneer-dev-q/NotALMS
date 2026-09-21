from aiogram.types import InlineKeyboardMarkup as IKM, InlineKeyboardButton as IKB
from aiogram.utils.keyboard import InlineKeyboardBuilder


COLOR_NAMES = {
    '#6366f1': 'индиго', '#f472b6': 'розовый', '#4ade80': 'зеленый', '#facc15': 'желтый',
    '#38bdf8': 'небо', '#f97316': 'оранжевый', '#a78bfa': 'сирень', '#ef4444': 'красный',
}


async def main_generateAuthKeyboard(username: str) -> IKM:
    keyboard = IKM(
        inline_keyboard=[
            [IKB(text='🧩 Регистрация в боте NotALMS',
                callback_data=f'registration:{username}', style='success')],
            [IKB(text='❌ Отменить действие',
                callback_data='user_cancel_all', style='danger')]
        ]
    )
    return keyboard


async def main_back() -> IKM:
    return IKM(
        inline_keyboard=[[IKB(text='↖️ Назад', callback_data='user_menu')]]
    )


async def main_Keyboard() -> IKM:
    keyboard = IKM(
        inline_keyboard=[
            [IKB(text='🎉 Мои достижения', callback_data='user_achievements', style='primary'),
            IKB(text='🔮 Мои курсы', callback_data='user_courses', style='primary')],
            [IKB(text='⚡️ Новости платформы', callback_data='user_getNews', style='success')],
            [IKB(text='🔓 Войти на сайт', callback_data='user_login', style='success')],
            [IKB(text='⚙️ Настройки', callback_data='user_settings', style='success')]
        ]
    )
    return keyboard


async def main_refferer() -> IKM:
    return IKM(
        inline_keyboard=[[
            IKB(text='👤 Перейти в профиль ↱', url='https://lms.notawallet.sbs/profile', style='primary')
        ]]
    )


async def main_bindRequired(url: str) -> IKM:
    return IKM(
        inline_keyboard=[[
            IKB(text='Открыть сайт и привязать аккаунт', url=url, style='primary')
        ]]
    )


async def main_coursesBuilder(courses_list: list):
    builder = InlineKeyboardBuilder()
    for i, course in enumerate(courses_list):
        builder.add(IKB(text=f'📌 - {course.get("title", "undefined")}', callback_data=f'view_course:{i}'))
    builder.add(IKB(text='↖️ Назад', callback_data='user_menu'))
    builder.adjust(1)
    return builder.as_markup()


async def main_courseInfo() -> IKM:
    return IKM(
        inline_keyboard=[[IKB(text='↖️ К списку курсов', callback_data='user_courses')]]
    )


async def main_achievementsBuilder(ach_list: list):
    builder = InlineKeyboardBuilder()
    for key, text in ach_list:
        builder.add(IKB(text=f'🧩 {key}', callback_data=f'ach:{key}'))
    builder.add(IKB(text='↖️ Назад', callback_data='user_menu'))
    builder.adjust(1)
    return builder.as_markup()


async def main_newsBuilder(news_list: list):
    builder = InlineKeyboardBuilder()
    for i, n in enumerate(news_list):
        builder.add(IKB(text=f"{n.get('emoji', '📰')} {n.get('title', 'без названия')}", callback_data=f'news:{i}'))
    builder.add(IKB(text='↖️ Назад', callback_data='user_menu'))
    builder.adjust(1)
    return builder.as_markup()


async def main_settings(current_color: str | None) -> IKM:
    builder = InlineKeyboardBuilder()
    for hex_, name in COLOR_NAMES.items():
        mark = ' ✓' if hex_ == current_color else ''
        builder.add(IKB(text=f'{name}{mark}', callback_data=f'setcolor:{hex_}'))
    builder.adjust(2)
    builder.row(IKB(text='🔓 Отвязать аккаунт', callback_data='user_unbind'))
    builder.row(IKB(text='↖️ Назад', callback_data='user_menu'))
    return builder.as_markup()


async def main_unlinkConfirm() -> IKM:
    return IKM(
        inline_keyboard=[
            [IKB(text='Да, отвязать', callback_data='user_unbind_yes', style='danger')],
            [IKB(text='Отмена', callback_data='user_settings')]
        ]
    )


async def main_loginLink(url: str) -> IKM:
    return IKM(
        inline_keyboard=[
            [IKB(text='🔓 Войти на сайт', url=url)],
            [IKB(text='↖️ Назад', callback_data='user_menu')]
        ]
    )
