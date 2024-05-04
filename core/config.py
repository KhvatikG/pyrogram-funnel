from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_ID: str
    API_HASH: str

    DB_URL: str
    DB_ECHO = True

    SKIP_TRIGGERS = {'Триггер1', }  # Триггеры для пропуска сообщения
    FINAL_TRIGGERS = {'прекрасно', 'ожидать'}  # Тригеры для окончания воронки
    TEXTS = {'msg1': 'Текст1',  # Текст сообщений
             'msg2': 'Текст2',
             'msg3': 'Текст3'
             }


settings = Settings()
