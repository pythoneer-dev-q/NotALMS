from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.utils.deep_linking import decode_payload
import back.auth.bot.utils.keyboards as kb
import back.auth.bot.databaseAuth.database as db
import back.auth.bot.utils.utils as ut
from back.auth.bot.utils import api
import random
import asyncio

vrouter = Router()

@vrouter.message(CommandStart(deep_link=True))
async def main_starter(message: Message, command: CommandObject):
    username = decode_payload(command.args)
    await message.answer(f'Добро пожаловать, <i><b>{username}</b></i>', reply_markup=await kb.main_generateAuthKeyboard(username=username))
    
@vrouter.callback_query(F.data.startswith('registration'))
async def userReg(call: CallbackQuery):
    await call.message.answer('Регистрация..')
    if await api.set_user_TG(user_id=call.from_user.id, username=call.data.split(':')[1]) == 'success':
        await call.message.edit_text('<b>💡 Главное меню</b>', reply_markup=await kb.main_Keyboard())
    else:
        await call.message.edit_text('Регистрация завершилась с ошибками. Попробуйте получить ссылку в профиле.')

@vrouter.message(CommandStart())
async def main_userCabinet(message: Message):
    await message.answer('<b>💡 Главное меню</b>', reply_markup=await kb.main_Keyboard())

@vrouter.callback_query(F.data.startswith('user_'))
async def main_functions(call: CallbackQuery):
    match call.data[5:]:
        case 'cancel_all':
            await call.message.edit_text('❌ <b>Действие отменено.</b>\n\nЧтобы зарегистрироваться заново, нужно получить ссылку в личном кабинете.')
        case 'achievements':
            await call.message.edit_text(f'<b>🧩 Достижения на платформе</b>\n\n<i>Достижения - важный шаг к познанию и обучению, они разработаны, дабы благодарить учеников за их труды и старания</i>\nНажмите на любое из них и получите по нему информацию\n\n{await api.main_get_userAchievements(call.from_user.id)}')
        case 'courses':
            await call.message.edit_text(f'<b>✅ Доступные курсы</b>\n\n<i>Это курсы, к которым имеет доступ только ваша роль (<b>у вас сейчас: "user"</b>). Отельной роли назначаются отдельные курсы. Посмотрите их ниже.</i>\n\n{await api.main_get_userCourses(call.from_user.id)}')
        case '':
            pass
        case _:
            await call.answer('Запретная зона...')