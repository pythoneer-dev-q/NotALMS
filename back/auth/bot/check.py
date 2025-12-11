from main import main_GenerateLink
import asyncio

async def main():
    print(await main_GenerateLink(
        username=input(),
        pswd=input()
    ))

if __name__ == '__main__':
    asyncio.run(main())