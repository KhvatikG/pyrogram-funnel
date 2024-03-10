import asyncio
import re

import asyncpg
from pyrogram import Client, filters, errors
from pyrogram.types import Message
# import betterlogging as logging
from datetime import datetime, timedelta, UTC
from loguru import logger
from conf import API_ID, API_HASH, DATABASE_URI

logger.add('logs/log.log', rotation='10 mb', level='DEBUG')

SKIP_TRIGGER = 'Тригер1'
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
    conn = await get_db_connection()

    # Выполняем SQL-запросы для создания таблиц
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
        id integer PRIMARY KEY,
        state TEXT NOT NULL DEFAULT 'new_user' CHECK (state IN ('new_user', 'msg1_sent', 'msg2_sent', 'msg3_sent')),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp,
        status TEXT NOT NULL DEFAULT 'alive' CHECK (status IN ('alive', 'dead', 'finished')),
        status_updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp)
    ''')

    await conn.close()


# Вставка нового пользователя
async def insert_user(conn, user_id: int):
    """
    Добавляет нового пользователя в db

    :param conn: обьект Connection db
    :param user_id: id юзера
    """
    await conn.execute('''
        INSERT INTO users(id) VALUES($1)
        ON CONFLICT(id) DO NOTHING;
    ''', user_id)


# Обновление статуса пользователя
async def update_user_status(conn, user_id: int, status: str):
    """
    Заменяет статус юзера в db на необходимый.

    :param conn: обьект Connection postgres db
    :param user_id: id юзера у которого меняем статус
    :param status: целевой статус на который будет производиться замена
    """
    await conn.execute('''
        UPDATE users SET status = $2, status_updated_at = $3 WHERE id = $1;
    ''', user_id, status, datetime.now(UTC))


async def update_user_state(conn, user_id: int, state: str):
    """
        Заменяет состояние юзера в db на необходимое.

        :param conn: обьект Connection postgres db
        :param user_id: id юзера у которого меняем статус
        :param state: целевое состояние на которое будет производиться замена
        """
    await conn.execute('''
            UPDATE users SET state = $2 WHERE id = $1;
        ''', user_id, state)


async def send_message(client: Client, user_id: int, message_text: str, state: str | None = None):
    """
    Отправляет сообщение юзеру с id user_id и обновляет статус alive в случае удачи
    В случае исключений UserIsBlocked, UserBlocked, UserDeactivated меняет статус юзера на dead

    :param client: обьект client класса Client
    :param user_id: id юзера которому отправляем сообщение
    :param message_text: текст сообщения
    :param state: по умолчанию None, если указан, меняет state юзера на указанный в случае удачной отправки
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
        logger.warning(f'Исключение {exc} при отправке пользователю{user_id}')
        await update_user_status(conn, user_id, 'dead')
        await conn.close()

    except Exception as exc:
        logger.error(f'Непридвиденная ошибка при отправке сообщения: {exc}')


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
                minutes=3)  # timedelta(minutes=39) if user['state'] == 'msg1_sent' else None
            msg3_time = status_updated_at + timedelta(
                minutes=5)  # timedelta(days=1, hours=2) if user['state'] == 'msg2_sent' else None

            match state:
                case 'new_user':
                    if current_time >= msg1_time:
                        # Чекаем файнал триггеры
                        await send_message(client, user_id, TEXTS['msg1'], 'msg1_sent')  # Отправляем Текст1
                        # Если удачно отправили бновляем статус что все ещё alive(можно просто обновить время статуса)
                        # Если неудачно меняем статус на dead и фиксируем время
                        # Обновляем время обновления статуса
                        # Меняем state на msg1_sent
                        pass
                case 'msg1_sent':
                    if current_time >= msg2_time:
                        # Чекаем файнал триггеры
                        # Чекаем Тригер1 -> продолжаем либо пропускаем(пропуск тоже фиксим по времени)
                        await send_message(client, user_id, TEXTS['msg2'], 'msg2_sent')  # Отправляем Текст2
                        # Если удачно отправили бновляем статус что все ещё alive(можно просто обновить время статуса)
                        # Если неудачно меняем статус на dead и фиксируем время
                        # Обновляем время обновления статуса
                        # Меняем state на msg2_sent
                        pass
                case 'msg2_sent':
                    if current_time >= msg3_time:
                        # Чекаем файнал триггеры
                        await send_message(client, user_id, TEXTS['msg3'], 'msg3_sent')  # Отправляем Текст2
                        # Если удачно отправили бновляем статус что все ещё alive(можно просто обновить время статуса)
                        # Если неудачно меняем статус на dead и фиксируем время
                        # Меняем state на msg3_sent

                        pass

            # Получаем список сообщений для поиска тригера
            messages = client.get_chat_history(user_id, limit=10)
            # Получаем свой id
            my = await client.get_me()
            my_id = my.id

            # Итерируем по сообщениям в чате с пользователем и ищем в исходящих триггер
            async for message in messages:
                # Получаем список слов сообщения для проверки на триггер
                message_str = message.text.lower()
                clear_message_str = re.sub(r'[^\w\s]', '', message_str)
                message_words = set(clear_message_str.split())

                if (message.from_user.id == my_id) and (FINAL_TRIGGERS & message_words):
                    # Нашли final триггер
                    ...  # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
                elif state == 'msg1_sent':
                    pass  # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

            await client.send_message(user_id, 'тест')
            await asyncio.sleep(1)

        await asyncio.sleep(10)


async def start_handler(client):
    @client.on_message()
    async def handle_message(client: Client, message: Message):
        if message.text == 'тест1':
            await message.forward('me')

            conn = await get_db_connection()
            await insert_user(conn=conn, user_id=message.from_user.id)
            await conn.close()


async def main():
    # logging.basic_colorized_config(level=logging.INFO)
    client = Client(name='me_client', api_id=API_ID, api_hash=API_HASH)

    await init_db()
    await client.start()
    await start_handler(client)
    await start_sender(client)

    await client.stop()


if __name__ == '__main__':
    asyncio.run(main())
