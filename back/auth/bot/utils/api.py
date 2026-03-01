from back.server.database import usersDB, coursesDB

async def set_user_TG(user_id: int, username: str):
    return 'success' if await usersDB.settg(user_id, to_user=username) is True else 'false'

async def search_user(user_id: int):
    return await usersDB.search_usersByTelegram(user_id)
async def main_get_userAchievements(user_id: int):
    return await usersDB.search_usersByTelegram(user_id)

async def main_get_userCourses(user_id: int):
    return await coursesDB.search_courses(role='user')