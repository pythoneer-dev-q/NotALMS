from back.auth.bot.config.authConfig import OTPLEN as length
import back.auth.bot.databaseAuth.database as db
import random

async def GenerateOTP(user_id: int):
    max_attempts = 10
    for _ in range(max_attempts):
        otp_list = [random.randint(0, 9) for _ in range(length)]
        otp = ''.join(map(str, otp_list))
        if await db.isExistOTP(otp, user_id) is None:
            return otp
    else:
        return None


async def GenerateLoginCode(user_id: int) -> str | None:
    # код для входа на сайт по тг
    for _ in range(10):
        code = ''.join(str(random.randint(0, 9)) for _ in range(6))
        if not await db.auth_collection.find_one({'code': code, 'used': False}):
            await db.save_login_code(user_id, code)
            return code
    return None
