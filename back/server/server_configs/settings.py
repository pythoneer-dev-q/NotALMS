# ! back/server/server_configs/settings.py
# все настройки из .env, тут только значения по умолчанию
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='ignore'
    )

    # сеть
    host: str = '127.0.0.1'
    port: int = 8004
    front_host: str = '127.0.0.1'
    front_port: int = 8005

    # ssl, пусто = обычный http
    ssl_certfile: str = ''
    ssl_keyfile: str = ''

    # cors, через запятую; '*' = все (только для разработки)
    cors_origins: str = '*'

    # mongo
    mongo_uri: str = 'mongodb://localhost:27017/'
    mongo_cluster: str = 'ntlms'
    mongo_users: str = 'nt_users'
    mongo_lmscluster: str = 'ntlmsdata'
    mongo_lmslessons: str = 'ntlessons'
    mongo_lmscoursesdata: str = 'ntcourses'
    mongo_lmsprogress: str = 'ntprogress'
    mongo_lmstasks: str = 'nttasks'
    mongo_lmstests: str = 'nttests'
    mongo_lmsreads: str = 'ntlesson_reads'  # прочитанные уроки

    # jwt
    secret_key: str = 'твой_очень_длинный_секрет_1234567890abcde99999999'
    algorithm: str = 'HS256'
    access_token_expire_minutes: int = 10080  # 7 дней

    # бот
    bot_token: str = ''
    bot_db_name: str = 'ntlmsauth'
    otplen: int = 6

    # производительность
    workers: int = 1
    mongo_max_pool: int = 100
    cache_ttl: int = 60        # кэш списка курсов, сек; 0 = выключить
    rate_limit: str = '20/minute'

    # redis для горячих данных; пусто = только память процесса
    redis_url: str = ''

    # пароль админки (front/assets/static/adminsecret.html)
    admin_secret: str = ''

    # публичный адрес фронта — бот строит из него ссылки (вход по коду и т.п.)
    public_url: str = 'http://127.0.0.1:8005'

    @property
    def cors_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if raw in ('*', ''):
            return ['*']
        return [o.strip() for o in raw.split(',') if o.strip()]


settings = Settings()
