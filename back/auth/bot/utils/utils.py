from config.authConfig import OTPLEN as length
import databaseAuth.database as db
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