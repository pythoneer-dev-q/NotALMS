from aiogram.types import InlineKeyboardMarkup as IKM, InlineKeyboardButton as IKB

async def main_generateAuthKeyboard(username: str, pswd: str, user_id: str) -> IKM:
    keyboard = IKM(
        inline_keyboard=[
            [
                IKB(text="🎉 Авторизоваться", callback_data=f"auth:{username}:{pswd}:{user_id}")
            ],
            [
                IKB(text="❌ Отмена", callback_data="cancel")
            ]
        ]
    )
    return keyboard

async def main_generateOTPKeyboard(otp: str, for_user: str) -> IKM:
    keyboard = IKM(
        inline_keyboard=[
            [
                IKB(text=f"OTP: {otp}", callback_data=f"None")
            ],
            [
                IKB(text="✅ Закрыть (код введен)", callback_data=f"check:{for_user}:{otp}"),
            ]
        ]
    )
    return keyboard