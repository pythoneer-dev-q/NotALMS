from pydantic import BaseModel, Field
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
    description: str = Field(max_length=500)
    order: int = -1
    cover: str
    is_published: bool = False
    difficulty: str
    tags: list[str]
    lessons: list[str]
    granted_to: list[str]
    role_ids: list[str] = []
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
    """
        _id - ид задания,
        lesson_id - привязка к уроку,
        type - тип задания,
        mode - /v1/tasks/{mode} эндпоинт для проверки,
        difficulty - сложность (по умолчанию -- легко),
        settings - настройки для задания {mode}
        created_at - временная метка
    """
class RegVisibleTask(BaseModel):
  id: str
  title: str = ''
  lesson_id: str
  type_task: str
  mode: str
  difficulty: str
  settings: dict
  hint_mode: str = 'solution'
  hint_text: str = ''

class UserRequest(BaseModel):
  click_from: str


# правка курса из админки: все поля опциональны, None не пишется
class AdminCourseUpdate(BaseModel):
    title: str | None = None
    description: str | None = Field(default=None, max_length=500)
    difficulty: str | None = None
    tags: list[str] | None = None
    order: int | None = None
    is_published: bool | None = None
    granted_to: list[str] | None = None
    lessons: list[str] | None = None
    cover: str | None = None
    role_ids: list[str] | None = None


# правка урока: контент-блоки, заголовок, порядок, тип
class AdminLessonUpdate(BaseModel):
    title: str | None = None
    content: list[dict] | None = None
    order: int | None = None
    type: str | None = None


# правка задачи: mode / settings / difficulty / type / привязка к уроку
class AdminTaskUpdate(BaseModel):
    title: str | None = None
    lesson_id: str | None = None
    mode: str | None = None
    difficulty: str | None = None
    settings: dict | None = None
    type_task: str | None = None
    hint_mode: str | None = None
    hint_text: str | None = None


# ===== новости =====
class AdminNewsCreate(BaseModel):
    id: str | None = None          # свой id (необязательно)
    title: str
    text: str = ''
    emoji: str = ''
    image: str = ''                # ссылка на картинку-обложку
    tags: list[str] = []
    order: int = 0
    is_published: bool = False


class AdminNewsUpdate(BaseModel):
    title: str | None = None
    text: str | None = None
    emoji: str | None = None
    image: str | None = None
    tags: list[str] | None = None
    order: int | None = None
    is_published: bool | None = None


class AdminSupportUpdate(BaseModel):
    email: str = ''
    telegram: str = ''
