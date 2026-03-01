from aiogram.types import InlineKeyboardMarkup as IKM, InlineKeyboardButton as IKB
from aiogram.utils.keyboard import InlineKeyboardBuilder

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


async def main_Keyboard() -> IKM:
    keyboard = IKM(
        inline_keyboard=[
            [IKB(text='🎉 Мои достижения', callback_data='user_achievements', style='primary'),
            IKB(text='🔮 Мои курсы', callback_data='user_courses', style='primary')],
            [IKB(text='⚡️ Новости платформы', callback_data='user_getNews', style='success')],
            [IKB(text='⚒️ Настройки', callback_data='user_settings', style='success'), 
            IKB(text='🧩 API', callback_data='user_devAPI', style='primary')]
        ]
    )
    return keyboard

async def main_refferer() -> IKM:
    return IKM(
        inline_keyboard=[[
            IKB(text='👤 Перейти в профиль ↱', url='https://lms.notawallet.sbs/profile', style='primary')
        ]]
    )

async def main_coursesBuilder(courses_list: list):
    builder = InlineKeyboardBuilder()
    for course in courses_list:
        builder.add(IKB(text=f'📌 - {course.get('title', 'undefined')}', callback_data=f'view_course:{course.get('title', 'undefined')}'))
    builder.add(IKB(text='↖️ Назад', callback_data='user_courses'))