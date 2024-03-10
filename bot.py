import asyncio
from pyrogram import Client
from pyrogram.types import Message
from datetime import datetime, timedelta, UTC
from logger import logger

from tools import (insert_user, update_user_status, update_user_state,
                   send_message, check_for_triggers, get_db_connection)

from conf import API_ID, API_HASH

# Можно перенести в конфиг
SKIP_TRIGGERS = {'Триггер1', }
FINAL_TRIGGERS = {'прекрасно', 'ожидать'}
TEXTS = {'msg1': 'Текст1',
         'msg2': 'Текст2',
         'msg3': 'Текст3'
         }


async def init_db():
    # Подключаемся к базе данных
    try:
        conn = await get_db_connection()

        # Выполняем запросы для создания таблиц
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
            id integer PRIMARY KEY,
            state TEXT NOT NULL DEFAULT 'new_user' CHECK (
            state IN ('new_user', 'msg1_sent', 'msg2_sent', 'msg2_skip', 'msg3_sent')),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp,
            status TEXT NOT NULL DEFAULT 'alive' CHECK (status IN ('alive', 'dead', 'finished')),
            status_updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT current_timestamp)
        ''')

        await conn.close()
        logger.debug(f'db init done')
    except Exception as exc:
        logger.critical(f'db init err: {exc}')


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
        if message.text == 'тест1':  # Для теста
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
