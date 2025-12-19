from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from handlers.httpbearer import get_current_user

crouter = APIRouter(prefix='/v1')


@crouter.get('/courses')
async def zagl(user=Depends(get_current_user)):
    return JSONResponse(
        content=[
            {
                "id": "python-basic",
                "title": "Python с нуля",
                "description": "Основы Python, переменные, циклы, функции"
            },
            {
                "id": "algorithms",
                "title": "Алгоритмы",
                "description": "Массивы, сортировки, сложность"
            },
            {
                "id": "algorithms",
                "title": f"Алгоритмы от {user['user_uid']}",
                "description": "Массивы, сортировки, сложность"
            },

        ], status_code=200

    )
