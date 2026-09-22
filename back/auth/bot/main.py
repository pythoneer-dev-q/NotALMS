import asyncio
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties as DefProp
from back.auth.bot.config.authConfig import TOKEN
from back.auth.bot.handlers.handlers import vrouter
from back.auth.bot.databaseAuth import database as bot_database
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
    instance = bot or Bot(
        token=TOKEN,
        default=DefProp(parse_mode='HTML', disable_notification=True)
    )
    return await create_start_link(bot=instance, payload=f"{username}", encode=True)

async def main():
    if not TOKEN:
        raise RuntimeError('BOT_TOKEN не задан в .env, бот не запустится')
    dp.include_router(vrouter)
    await bot_database.ensure_indexes()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
