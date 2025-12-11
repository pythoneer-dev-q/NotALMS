from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.utils.deep_linking import decode_payload
import utils.keyboards as kb
import databaseAuth.database as db
import utils.utils as ut
import random
import asyncio

vrouter = Router()

@vrouter.message(CommandStart(deep_link=True))
async def main_starter(message: Message, command: CommandObject):
    username, pswd = decode_payload(command.args).split(':')
    if isinstance(decode_payload(command.args).split(':')[0], str):
        if (tmp := await db.find_user(message.from_user.id, username)) is None:
            await db.register_user(user_id=message.from_user.id, 
                                   username=username,
                                   pswd=pswd)
            wlcm_msg = await message.answer(f"Здравствуйте, <i>{username}!</i>\nВаш пароль: <code>{pswd}</code>\n\n<b>Нажмите кнопку ниже</b>, чтобы авторизоваться.",
                                             reply_markup=await kb.main_generateAuthKeyboard(user_id=message.from_user.id,
                                                                                    username=username,
                                                                                    pswd=pswd))
            await wlcm_msg.pin()
        else:
            wlcm_msg = await message.answer(f"Возможно, вы уже подтвердили свой доступ.")

    else:
        wlcm_msg = await message.answer(f"Здравствуйте, <i>{username}!</i>\nВаш пароль: <code>{pswd}</code>\n\n<b🤷‍♂️ >Вы уже подтвердили свой аккаунт</b>")

@vrouter.callback_query(F.data.startswith('auth:'))
async def main_GenerateOTPAuth(call: CallbackQuery):
    _, username, pswd, user_id = call.data.split(':')
    tmp = await ut.GenerateOTP(user_id=call.from_user.id)
    if tmp is not None:
        for i in range(random.randint(0, 7)):
            await call.message.edit_text(f'{[
                '🕐', '🕑', '🕓', '🕔', '🕥', '🕛', '⚠️'
            ][i]} Генерация кода ')
            await asyncio.sleep(0.7)
        await call.message.edit_text(text=
            f'Ваш код: <code>{tmp}</code> (click2copy)\n\n'
            f'<b>Данные для входа (на всякий случай)</b>:'
            f'<blockquote><b>Ваш логин:</b> <i>{username}</i>\n<b>Ваш пароль:</b> <code>{pswd}</code></blockquote>',
            reply_markup=await kb.main_generateOTPKeyboard(otp=tmp, for_user=call.from_user.id)
        )

@vrouter.callback_query(F.data.startswith('check:'))
async def maindel(call: CallbackQuery):
    await call.message.edit_text(f"Данные будут удалены:\n{'<code>#</code' * 8}>")