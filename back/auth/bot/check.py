from back.auth.bot.main import main_GenerateLink
import asyncio

async def main():
    # раньше передавался лишний pswd
    print(await main_GenerateLink(
        username=input()
    ))

if __name__ == '__main__':
    asyncio.run(main())