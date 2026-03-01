import asyncio
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties as DefProp
from back.auth.bot.config.authConfig import TOKEN
from back.auth.bot.handlers.handlers import vrouter
from aiogram.utils.deep_linking import create_start_link

bot = Bot(
        token=TOKEN,
        default=DefProp(parse_mode='HTML', disable_notification=True)
        )
dp = Dispatcher(

)
async def main_GenerateLink(username: str):
    return await create_start_link(bot=bot, payload=f"{username}", encode=True)
async def main():
    dp.include_router(vrouter)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())