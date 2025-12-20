from pydantic import BaseModel
""" _id - ид курса
        title - заголовок для сайта
        description - описание под карточку
        cover[optional] - обложка для курса
        difficulty - сложность
        lessons[idS] - id уроков для курса
        granted_to - разрешеные группы пользователей
"""


class RegVisibleCourse(BaseModel):
    id: str
    title: str
    description: str
    order: int = -1
    cover: str
    is_published: bool = False
    difficulty: str
    tags: list[str]
    lessons: list[str]
    granted_to: list[str]
"""{
  "_id": "dna_structure",
  "course_id": "dna_basic",
  "title": "Строение ДНК",
  "type": "theory",
  "order": 2,
  "content": [
    {
      "type": "text",
      "value": "ДНК состоит из двух антипараллельных цепей."
    },
    {
      "type": "image",
      "src": "/static/img/dna.png",
      "alt": "Структура ДНК"
    },
    {
      "type": "list",
      "items": [
        "Аденин",
        "Тимин",
        "Гуанин",
        "Цитозин"
      ]
    },
  ]
}"""
class RegVisibleLesson(BaseModel):
    id: str
    title: str
    course_id: str
    type: str
    order: int = -1
    content: list[dict]