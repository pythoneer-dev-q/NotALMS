from aiogram.types import InlineKeyboardMarkup as IKM, InlineKeyboardButton as IKB


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
             IKB(text='🔮 Доступные курсы', callback_data='user_courses', style='primary')],
            [IKB(text='⚡️ Новости платформы', callback_data='user_getNews', style='success')],
            [IKB(text='⚒️ Настройки', callback_data='user_settings', style='success'), 
             IKB(text='🧩 API (разработчики)', callback_data='user_devAPI', style='primary')]
        ]
    )
    return keyboard
