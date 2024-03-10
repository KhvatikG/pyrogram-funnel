import asyncio
import re

import asyncpg
from pyrogram import Client, errors
from pyrogram.types import Message
from datetime import datetime, timedelta, UTC
from loguru import logger
from conf import API_ID, API_HASH, DATABASE_URI

logger.add('logs/log.log', rotation='10 mb', level='DEBUG')

SKIP_TRIGGERS = {'Триггер1', }
FINAL_TRIGGERS = {'прекрасно', 'ожидать'}
TEXTS = {'msg1': 'Текст1',
         'msg2': 'Текст2',
         'msg3': 'Текст3'
         }


async def get_db_connection():
    return await asyncpg.connect(DATABASE_URI)


# Инициализация
async def init_db():
    # Подключаемся к базе данных
    try:
        conn = await get_db_connection()

        # Выполняем SQL-запросы для создания таблиц
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
            id integer PRIMARY KEY,
            state TEXT NOT NULL DEFAULT 'new_user' CHECK (state IN ('new_user', 'msg1_sent', 'msg2_sent', 'msg2_skip', 'msg3_sent')),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp,
            status TEXT NOT NULL DEFAULT 'alive' CHECK (status IN ('alive', 'dead', 'finished')),
            status_updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp)
        ''')

        await conn.close()
        logger.debug(f'db init done')
    except Exception as exc:
        logger.critical(f'db init err: {exc}')


# Вставка нового пользователя
async def insert_user(conn, user_id: int):
    """
    Добавляет нового пользователя в db

    :param conn: объект Connection db
    :param user_id: id юзера
    """
    try:
        await conn.execute('''
            INSERT INTO users(id) VALUES($1)
            ON CONFLICT(id) DO NOTHING;
        ''', user_id)
    except Exception as exc:
        logger.critical(f'Неудалось добавить пользователя {user_id} в базу данных: {exc}')


# Обновление статуса пользователя
async def update_user_status(conn, user_id: int, status: str):
    """
    Заменяет статус юзера в db на необходимый.

    :param conn: объект Connection postgres db
    :param user_id: id юзера у которого меняем статус
    :param status: целевой статус на который будет производиться замена
    """
    try:
        await conn.execute('''
            UPDATE users SET status = $2, status_updated_at = $3 WHERE id = $1;
        ''', user_id, status, datetime.now(UTC))
        logger.info(f'{user_id} статус обновлен на {status}')
    except Exception as exc:
        logger.critical(f'Не удалось сменить статус юзеру {user_id}: {exc}')


async def update_user_state(conn, user_id: int, state: str):
    """
        Заменяет состояние юзера в db на необходимое.

        :param conn: обьект Connection postgres db
        :param user_id: id юзера у которого меняем статус
        :param state: целевое состояние на которое будет производиться замена
        """
    try:
        await conn.execute('''
                UPDATE users SET state = $2 WHERE id = $1;
            ''', user_id, state)
        logger.info(f'{user_id} состояние изменено на {state}')
    except Exception as exc:
        logger.critical(f'Не удалось сменить состояние юзеру {user_id} - {exc}')


async def send_message(client: Client, user_id: int, message_text: str, state: str | None = None):
    """
    Отправляет сообщение юзеру с id user_id и обновляет статус alive в случае удачи
    В случае исключений UserIsBlocked, UserBlocked, UserDeactivated меняет статус юзера на dead

    :param client: обьект client класса Client
    :param user_id: id юзера, которому отправляем сообщение
    :param message_text: текст сообщения
    :param state: по умолчанию None, если указан, меняет state юзера на указанный, в случае удачной отправки
    """
    conn = await get_db_connection()
    try:
        await client.send_message(user_id, message_text)
        if state:
            await update_user_state(conn, user_id, state)
        await update_user_status(conn, user_id, 'alive')
        await conn.close()
        logger.info(f'Сообщение {message_text} успешно отправлено пользователю {user_id}')
    except errors.UserIsBlocked or errors.UserBlocked or errors.UserDeactivated as exc:
        logger.warning(f'Исключение при отправке пользователю{user_id}: {exc}')
        await update_user_status(conn, user_id, 'dead')
        await conn.close()

    except Exception as exc:
        logger.error(f'Непредвиденная ошибка при отправке сообщения: {exc}')


async def check_for_triggers(
        client: Client,
        user_id: int,
        final_triggers: set,
        skip_triggers: set = None,
        limit: int = 30
) -> str | None:
    """
    Проверяет исходящие сообщения к пользователю на наличие триггеров.
    Если найдены триггеры окончания воронки, то возвращает строку - 'final';
    Если найдены триггеры пропуска сообщения, то строку - 'skip';
    В случае когда триггеры в сообщениях не найдены возвращает значение - None

    :param client: объект client класса Client
    :param user_id: id юзера в сообщения к которому производить поиск
    :param final_triggers: список тригеров окончания воронки для поиска(множество)
    :param skip_triggers: список тригеров пропуска сообщения для поиска(множество)
    :param limit: лимит кол-ва сообщений для проверки на триггеры
    """

    # Получаем список сообщений для поиска тригера
    messages = client.get_chat_history(user_id, limit=limit)

    # Приводим триггеры к нижнему регистру
    final_triggers = {trigger.lower() for trigger in final_triggers}
    skip_triggers = {trigger.lower() for trigger in skip_triggers}

    # Получаем свой id
    my = await client.get_me()
    my_id = my.id

    # Итерируем по сообщениям в чате с пользователем и ищем в исходящих триггер
    async for message in messages:

        if message.from_user.id == my_id:  # Если сообщение от нас
            # Получаем список слов сообщения для проверки на триггер
            message_str = message.text.lower()  # Приводим к нижнему регистру
            clear_message_str = re.sub(r'[^\w\s]', '', message_str)  # Удаляем пунктуацию
            message_words = set(clear_message_str.split())  # Получаем множество слов сообщения

            if final_triggers & message_words:  # Если сообщение содержит финализирующий триггер
                return 'final'

            elif skip_triggers and (skip_triggers & message_words):
                return 'skip'

            else:
                return None


async def start_sender(client: Client):
    conn = await get_db_connection()
    while True:
        current_time = datetime.now(UTC)
        # Получаем пользователей со статусом alive
        users = await conn.fetch("SELECT * FROM users WHERE status = 'alive';")

        # Итерируемм по юзерам
        for user in users:
            user_id = user['id']
            status_updated_at = user['status_updated_at']
            state = user['state']

            # Время для отправки
            msg1_time = status_updated_at + timedelta(minutes=1)  # timedelta(minutes=6)
            msg2_time = status_updated_at + timedelta(
                minutes=1)  # timedelta(minutes=39) if user['state'] == 'msg1_sent' else None
            msg3_time = status_updated_at + timedelta(
                minutes=1)
            # timedelta(days=1, hours=2) if (user['state'] == 'msg2_sent' or user['state'] == 'msg2_skip' else None

            match state:
                case 'new_user':
                    if current_time >= msg1_time:
                        # Чекаем файнал триггеры
                        trigger_type = await check_for_triggers(client, user_id, FINAL_TRIGGERS)

                        if trigger_type:  # Если триггер найден
                            logger.info(f'Найден триггер {trigger_type} у пользователя {user_id}')
                            await update_user_status(conn, user_id, 'finished')
                        else:
                            logger.debug(f'new_user {user_id} триггеров не найдено')
                            await send_message(client, user_id, TEXTS['msg1'], 'msg1_sent')  # Отправляем Текст1
                        # Если удачно отправили бновляем статус что все ещё alive(можно просто обновить время статуса)
                        # Если неудачно меняем статус на dead и фиксируем время
                        # Обновляем время обновления статуса
                        # Меняем state на msg1_sent

                case 'msg1_sent':
                    if current_time >= msg2_time:
                        # Чекаем файнал триггеры
                        trigger_type = await check_for_triggers(client, user_id, FINAL_TRIGGERS, SKIP_TRIGGERS)
                        # Чекаем Тригер1 -> продолжаем либо пропускаем(пропуск тоже фиксим по времени)

                        match trigger_type:
                            case None:
                                logger.debug(f'msg1_sent {user_id} триггеров не найдено')
                                await send_message(client, user_id, TEXTS['msg2'], 'msg2_sent')  # Отправляем Текст2

                            case 'final':
                                logger.info(f'Найден триггер {trigger_type} у пользователя {user_id}')
                                await update_user_status(conn, user_id, 'finished')

                            case 'skip':
                                logger.info(f'Найден триггер {trigger_type} у пользователя {user_id}')
                                await update_user_state(conn, user_id, 'msg2_skip')
                                #  Нужно чекнуть что alive !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                                #  Обновляем время для отсчета следующего сообщения
                                await update_user_status(conn, user_id, 'alive')

                        # Если удачно отправили бновляем статус что все ещё alive(можно просто обновить время статуса)
                        # Если неудачно меняем статус на dead и фиксируем время
                        # Обновляем время обновления статуса
                        # Меняем state на msg2_sent

                case 'msg2_sent' | 'msg2_skip':
                    if current_time >= msg3_time:
                        # Чекаем файнал триггеры
                        trigger_type = await check_for_triggers(client, user_id, FINAL_TRIGGERS)

                        if trigger_type:  # Если триггер найден
                            logger.info(f'Найден триггер {trigger_type} у пользователя {user_id}')
                            await update_user_status(conn, user_id, 'finished')
                        else:
                            logger.debug(f'msg2_sent {user_id} триггеров не найдено')
                            await send_message(client, user_id, TEXTS['msg3'], 'msg3_sent')  # Отправляем Текст3

                        # Если удачно отправили бновляем статус что все ещё alive(можно просто обновить время статуса)
                        # Если неудачно меняем статус на dead и фиксируем время
                        # Меняем state на msg3_sent

            # await client.send_message(user_id, 'тест')
            await asyncio.sleep(0.3)

        await asyncio.sleep(30)


async def start_handler(client):
    @client.on_message()
    async def handle_message(_, message: Message):
        if message.text == 'тест1':
            await message.forward('me')

            conn = await get_db_connection()
            await insert_user(conn=conn, user_id=message.from_user.id)
            await conn.close()


async def main():
    client = Client(name='me_client', api_id=API_ID, api_hash=API_HASH)

    await init_db()
    await client.start()
    await start_handler(client)
    await start_sender(client)

    await client.stop()


if __name__ == '__main__':
    asyncio.run(main())
