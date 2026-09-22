import asyncio
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties as DefProp
from back.auth.bot.config.authConfig import TOKEN
from back.auth.bot.handlers.handlers import vrouter
from back.auth.bot.databaseAuth import database as bot_database
from back.server.runtime import configure_logging, install_loop_exception_handler
from aiogram.utils.deep_linking import create_start_link

# токена может не быть (api-процесс), тогда бот только генерит ссылки по запросу
bot = None
if TOKEN:
    bot = Bot(
            token=TOKEN,
            default=DefProp(parse_mode='HTML', disable_notification=True)
            )
dp = Dispatcher()

async def main_GenerateLink(username: str):
    # api-сервер зовет только это, polling тут не стартует
    if bot is not None:
        return await create_start_link(bot=bot, payload=f"{username}", encode=True)
    if not TOKEN:
        raise RuntimeError('BOT_TOKEN is not configured')
    instance = Bot(token=TOKEN, default=DefProp(parse_mode='HTML', disable_notification=True))
    try:
        return await create_start_link(bot=instance, payload=f"{username}", encode=True)
    finally:
        await instance.session.close()

async def main():
    if not TOKEN:
        raise RuntimeError('BOT_TOKEN не задан в .env, бот не запустится')
    configure_logging()
    install_loop_exception_handler()
    dp.include_router(vrouter)
    await bot_database.ensure_indexes()
    try:
        await dp.start_polling(bot)
    finally:
        bot_database.close_client()
        if bot is not None:
            await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
