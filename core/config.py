from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_ID: str  # api_id телеграм
    API_HASH: str  # api_hash телеграм

    DB_URL: str  # url базы данных
    DB_ECHO: bool = True  # вывод команд базы данных

    SKIP_TRIGGERS: set = {'Триггер1', }  # Триггеры для пропуска сообщения
    FINAL_TRIGGERS: set = {'прекрасно', 'ожидать'}  # Тригеры для окончания воронки
    TEXTS: dict = {
        'msg1': 'Текст1',  # Текст сообщений
        'msg2': 'Текст2',
        'msg3': 'Текст3'
        }


settings = Settings()
