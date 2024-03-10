import asyncpg
from pyrogram import Client, errors
import re
from conf import DATABASE_URI
from logger import logger
from datetime import datetime, UTC


async def get_db_connection():
    return await asyncpg.connect(DATABASE_URI)


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


async def check_user_alive(client: Client, user_id: int, test_message: str = 'ㅤ'):
    """
    Проверяет является ли пользователь доступным для сообщений, по умолчанию отправляет неотображаемый символ,
    позволяет использовать любую строку в качестве тестового сообщения.

    Пытается отправить тестовое сообщение, в случае удачи удаляет его и обновляет статус 'alive' в db.
    В случае неудачи меняет статус на 'dead' в случаях UserIsBlocked | UserBlocked | UserDeactivated.
    В остальных случаях просто пишет ошибку в логи.

    :param client: объект client класса Client
    :param user_id: id юзера, alive которого нужно проверить
    :param test_message: текст тестового сообщения
    """

    conn = await get_db_connection()
    try:
        sent_message = await client.send_message(user_id, test_message)
        await client.delete_messages(user_id, message_ids=sent_message.id)

    except errors.UserIsBlocked or errors.UserBlocked or errors.UserDeactivated as exc:
        logger.warning(f'Исключение при проверке доступности пользователя{user_id}: {exc}')
        await update_user_status(conn, user_id, 'dead')
        await conn.close()

    except Exception as exc:
        logger.error(f'Непредвиденная ошибка при отправке сообщения: {exc}')


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
    :param final_triggers: список триггеров окончания воронки для поиска(множество)
    :param skip_triggers: список триггеров пропуска сообщения для поиска(множество)
    :param limit: лимит кол-ва сообщений для проверки на триггеры
    """

    # Получаем список сообщений для поиска триггера
    messages = client.get_chat_history(user_id, limit=limit)

    # Приводим триггеры к нижнему регистру
    final_triggers = {trigger.lower() for trigger in final_triggers}

    skip_triggers = {trigger.lower() for trigger in skip_triggers} if skip_triggers else None

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
