# NotALMS

Учебная платформа для интерактивных курсов.  
На старте — задания по молекулярной биологии (ДНК/РНК), дальше — любые дисциплины.

## Технологии

- **Бэкенд**: Python + FastAPI  
- **База данных**: MongoDB  
- **Фронтенд**: чистый HTML / CSS / JS (однофайловые страницы для простоты)  
- **Аутентификация**: JWT (stateless)  
- **Хэширование паролей**: bcrypt (через passlib)  

## Структура проекта

```
NotALMS/
├── back/
│   ├── auth/
│   │   └── bot/
│   │       ├── config/            # локальные конфиги (у каждого свои)
│   │       │   └── authConfig.py
│   │       ├── databaseAuth/      # БД для привязки Telegram (в будущем)
│   │       │   └── database.py
│   │       ├── handlers/          # роутеры бота
│   │       │   └── handlers.py
│   │       ├── utils/
│   │       │   ├── keyboards.py   # inline-клавиатуры
│   │       │   └── utils.py       # генерация OTP
│   │       ├── check.py           # проверка генерации входной ссылки
│   │       └── main.py            # основной файл бота (Dispatcher)
│   └── server/
│       ├── database/
│       │   ├── coursesDB.py       # работа с курсами (уроки, ресурсы, тесты)
│       │   ├── usersDB.py         # пользователи и регистрация
│       │   └── utils.py           # пароли / хэши / JWT
│       ├── handlers/
│       │   ├── apihandler_conf/
│       │   │   └── models.py      # модели входящих POST-запросов /v1
│       │   ├── fronthandler_conf/
│       │   │   └── ...            # временно пусто
│       │   ├── api_handler.py     # /v1/register, /login, /me и др.
│       │   ├── front_apHandler.py # /courses, /task и т.д.
│       │   └── httpbearer.py      # проверка JWT в каждом запросе
│       ├── server_configs/
│       │   └── server_mainConfig.py  # локальные настройки сервера
│       ├── tasks/                 # проверка заданий курсов
│       │   ├── task1.py
│       │   ├── task2.py
│       │   ├── task3.py
│       │   └── ...                # остальные задания
│       └── main.py                # запуск backend-сервера
│
├── front/
│   ├── assets/
│   │   ├── static/
│   │   │   ├── dash.html
│   │   │   └── index.html
│   │   └── reset/
│   │       └── reset.css
│   └── server/
│       ├── frontRouter.py
│       └── main.py
│
├── .gitignore
├── LICENSE (Apache 2.0)
└── README.md
```

## Запуск (локально)

1. Клонируй репозиторий  
2. Установи зависимости:
```bash
   pip install fastapi uvicorn motor python-dotenv passlib[bcrypt] python-jose[cryptography] slowapi
```

3. Создай файл `.env` в корне проекта (пример ниже)
4. Запусти MongoDB локально или используй MongoDB Atlas
5. Запусти сервер:

```bash
   uvicorn front.server.main:app --reload
```
6. Открой в браузере:
   [http://127.0.0.1:8004/index.html](http://127.0.0.1:8004/index.html) (или просто `/`)

## Пример `.env`

```
MONGO_URI=mongodb://localhost:27017/
MONGO_CLUSTER=ntlms
MONGO_USERS=nt_users
MONGO_COURSES=nt_courses

SECRET_KEY=очень_длинный_случайный_ключ_минимум_64_символа
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080  # 7 дней
```

## API (на данный момент)

Все эндпоинты имеют префикс `/v1`.

### Аутентификация

* `POST /v1/register` — регистрация (возвращает JWT)
* `POST /v1/login` — вход (возвращает JWT)
* `GET /v1/me` — данные текущего пользователя
  (Bearer-токен в заголовке `Authorization`)

### Задания по ДНК / РНК

* `POST /api/generate` — генерация задания

  ```json
  {
    "mode": 1,
    "length": 15
  }
  ```

  `length` — опционален

* `POST /api/check` — проверка ответа

  ```json
  {
    "mode": 1,
    "original_data": {},
    "user_answer": "5'-АУУУАЦГГУГГЦАААГГЦ-3'"
  }
  ```

### Режимы заданий

1. Построить мРНК по нижней (матричной) цепи ДНК
2. Построить мРНК по верхней (матричной) цепи ДНК
3. Построить комплементарную цепь ДНК (антипараллельно)

Проверка учитывает:

* концы 5' / 3'
* комплементарность
* антипараллельность
* длину цепи
* лишние или недопустимые символы

## Планы развития

* Дашборд с прогрессом пользователя
* Список курсов и уроков
* Сохранение результатов заданий
* Админ-панель
* Новые типы заданий (программирование, математика и др.)

## Лицензия

Проект учебный.
Свободно форкай и используй — улучшай как хочешь.

Проект разрабатываю самостоятельно, параллельно изучая вёрстку и FastAPI.
Вопросы и предложения приветствуются.
