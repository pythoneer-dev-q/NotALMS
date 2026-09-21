from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.utils.deep_linking import decode_payload
import back.auth.bot.utils.keyboards as kb
import back.auth.bot.databaseAuth.database as db
import back.auth.bot.utils.utils as ut
from back.auth.bot.utils import api
from back.server.server_configs.settings import settings
import random
import asyncio

vrouter = Router()


async def safe_answer(target: Message, text: str, markup=None):
    try:
        if markup:
            await target.edit_text(text, reply_markup=markup)
        else:
            await target.edit_text(text)
    except Exception:
        try:
            await target.answer(text, reply_markup=markup)
        except Exception:
            pass


async def menu_text(user_id: int) -> str:
    user = await api.search_user(user_id)
    name = (user or {}).get('user_login') or 'новичок'
    return (
        '<b>💡 Главное меню</b>\n\n'
        f'👤 <b>{name}</b>\n'
        f"★ рейтинг: {(user or {}).get('rating', 0)}\n\n"
        'выбирай раздел кнопками ниже'
    )


def bind_url() -> str:
    return settings.public_url.rstrip('/') + '/settings'


async def show_bind_required(target: Message):
    await safe_answer(
        target,
        '<b>Сначала привяжи аккаунт</b>\n\n'
        'Бот открывает меню и выдаёт код входа только после привязки Telegram в настройках сайта.',
        await kb.main_bindRequired(bind_url())
    )


def login_text(code: str) -> str:
    return (
        '<b>Вход на сайт</b>\n\n'
        f'Код: <code>{code}</code>\n\n'
        'Нажми кнопку ниже или введи код на странице входа. Код действует 5 минут и используется один раз.'
    )


async def show_menu(call: CallbackQuery):
    await call.answer()
    if not await api.search_user(call.from_user.id):
        await show_bind_required(call.message)
        return
    await safe_answer(call.message, await menu_text(call.from_user.id), await kb.main_Keyboard())


@vrouter.callback_query(F.data == 'user_menu')
async def main_backToMenu(call: CallbackQuery):
    # общий экран меню, сюда ведут все кнопки «назад»
    await show_menu(call)


@vrouter.message(Command('login'))
async def main_loginCode(message: Message):
    user = await api.search_user(message.from_user.id)
    if not user:
        await message.answer(
            '<b>Сначала привяжи аккаунт</b>\n\nОткрой настройки сайта и привяжи Telegram.',
            reply_markup=await kb.main_bindRequired(bind_url())
        )
        return
    code = await ut.GenerateLoginCode(message.from_user.id)
    if not code:
        await message.answer('не смог сгенерить ссылку, попробуй позже')
        return
    url = f"{settings.public_url.rstrip('/')}/tg/{code}"
    await message.answer(
        login_text(code),
        reply_markup=await kb.main_loginLink(url)
    )

@vrouter.message(CommandStart(deep_link=True))
async def main_starter(message: Message, command: CommandObject):
    if await api.search_user(message.from_user.id):
        await message.answer(await menu_text(message.from_user.id), reply_markup=await kb.main_Keyboard())
        return
    username = decode_payload(command.args)
    await message.answer(f'Добро пожаловать, <i><b>{username}</b></i>', reply_markup=await kb.main_generateAuthKeyboard(username=username))
    
@vrouter.callback_query(F.data.startswith('registration'))
async def userReg(call: CallbackQuery):
    await call.answer()
    if await api.set_user_TG(user_id=call.from_user.id, username=call.data.split(':')[1]) == 'success':
        await safe_answer(
            call.message,
            await menu_text(call.from_user.id),
            await kb.main_Keyboard()
        )
    else:
        await safe_answer(
            call.message,
            'Не удалось привязать аккаунт. Возможно, Telegram уже связан с другим профилем.',
            await kb.main_bindRequired(bind_url())
        )

@vrouter.message(CommandStart())
async def main_userCabinet(message: Message):
    if not await api.search_user(message.from_user.id):
        await message.answer(
            '<b>Сначала привяжи аккаунт</b>\n\nПосле привязки здесь появится меню, вход и курсы.',
            reply_markup=await kb.main_bindRequired(bind_url())
        )
        return
    await message.answer(await menu_text(message.from_user.id), reply_markup=await kb.main_Keyboard())

@vrouter.callback_query(F.data.startswith('user_'))
async def main_functions(call: CallbackQuery):
    await call.answer()
    if not await api.search_user(call.from_user.id):
        await show_bind_required(call.message)
        return
    match call.data[5:]:
        case 'cancel_all':
            await safe_answer(
                call.message,
                '❌ <b>Действие отменено.</b>\n\nЧтобы зарегистрироваться заново, нужно получить ссылку в личном кабинете.',
                await kb.main_back()
            )
        case 'achievements':
            ach = await api.main_get_userAchievementsRaw(call.from_user.id)
            if not ach:
                await safe_answer(call.message, '🧩 <b>Достижений пока нет</b>\n\nрешай задачи — здесь появятся награды', await kb.main_back())
                return
            await safe_answer(
                call.message,
                '<b>🧩 Достижения</b>\n\n<i>нажми на любое — покажу описание</i>',
                await kb.main_achievementsBuilder(ach)
            )
        case 'courses':
            lst = await api.main_get_userCoursesRaw(call.from_user.id)
            if not lst:
                await safe_answer(call.message, '📚 <b>Курсы пока нет</b>\n\nони появятся здесь, как только админ их опубликует', await kb.main_back())
                return
            await safe_answer(
                call.message,
                '<b>✅ Доступные курсы</b>\n\n<i>нажми на курс — покажу описание</i>',
                await kb.main_coursesBuilder(lst)
            )
        case 'getNews':
            news = await api.main_get_newsRaw()
            if not news:
                await safe_answer(call.message, '⚡️ <b>Новостей пока нет</b>', await kb.main_back())
                return
            await safe_answer(
                call.message,
                '<b>⚡️ Новости платформы</b>\n\n<i>нажми на новость — откроется полный текст</i>',
                await kb.main_newsBuilder(news)
            )
        case 'settings':
            color = await api.get_user_color(call.from_user.id)
            await safe_answer(
                call.message,
                '<b>⚙️ Настройки</b>\n\n🎨 выбери цвет имени — он будет на сайте и в топе\n🔓 отвязка отключит бота от аккаунта',
                await kb.main_settings(color)
            )
        case 'unbind':
            await safe_answer(
                call.message,
                '<b>🔓 Отвязать аккаунт?</b>\n\nбот перестанет быть привязан;\nпривязать заново можно через профиль на сайте',
                await kb.main_unlinkConfirm()
            )
        case 'unbind_yes':
            ok = await api.unbind_user(call.from_user.id)
            text = 'аккаунт отвязан. привязать заново можно через профиль на сайте' if ok else 'не смог отвязать, попробуй позже'
            await safe_answer(call.message, ('✅ ' if ok else '⚠️ ') + text, await kb.main_back())
        case 'login':
            user = await api.search_user(call.from_user.id)
            if not user:
                await safe_answer(call.message, 'сначала привяжи аккаунт через профиль на сайте', await kb.main_back())
                return
            code = await ut.GenerateLoginCode(call.from_user.id)
            if not code:
                await safe_answer(call.message, 'не смог сгенерить ссылку, попробуй позже', await kb.main_back())
                return
            url = f"{settings.public_url.rstrip('/')}/tg/{code}"
            await safe_answer(
                call.message,
                login_text(code),
                await kb.main_loginLink(url)
            )
        case _:
            await call.answer('Запретная зона...')


@vrouter.callback_query(F.data.startswith('view_course:'))
async def main_viewCourse(call: CallbackQuery):
    # карточка курса по индексу 
    await call.answer()
    idx = int(call.data.split(':', 1)[1])
    lst = await api.main_get_userCoursesRaw(call.from_user.id)
    if idx >= len(lst):
        await safe_answer(call.message, 'курс не найден, список обновился', await kb.main_coursesBuilder(lst))
        return
    c = lst[idx]
    await safe_answer(
        call.message,
        f'<b>📌 {c.get("title", "undefined")}</b>\n\n{c.get("description") or "описания пока нет"}',
        await kb.main_courseInfo()
    )


@vrouter.callback_query(F.data.startswith('ach:'))
async def main_viewAch(call: CallbackQuery):
    # описание конкретного достижения
    await call.answer()
    key = call.data.split(':', 1)[1]
    ach = await api.main_get_userAchievementsRaw(call.from_user.id)
    desc = next((t for k, t in ach if k == key), 'описания нет')
    await safe_answer(
        call.message,
        f'<b>🧩 {key}</b>\n\n{desc}',
        await kb.main_back()
    )


@vrouter.callback_query(F.data.startswith('news:'))
async def main_viewNews(call: CallbackQuery):
    # полный текст новости
    await call.answer()
    idx = int(call.data.split(':', 1)[1])
    news = await api.main_get_newsRaw()
    if idx >= len(news):
        return
    n = news[idx]
    await safe_answer(
        call.message,
        f"{n.get('emoji', '📰')} <b>{n.get('title', '')}</b>\n\n{n.get('text', '')}",
        await kb.main_back()
    )


@vrouter.callback_query(F.data.startswith('setcolor:'))
async def main_setColor(call: CallbackQuery):
    # цвет имени меняется
    await call.answer('цвет сохранен ✓')
    hex_ = call.data.split(':', 1)[1]
    if hex_ not in kb.COLOR_NAMES:
        return
    await api.set_user_color(call.from_user.id, hex_)
    color = await api.get_user_color(call.from_user.id)
    await safe_answer(
        call.message,
        '<b>⚙️ Настройки</b>\n\n🎨 цвет сохранен — на сайте обновится после перезагрузки страницы',
        await kb.main_settings(color)
    )
