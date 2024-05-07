from sqlalchemy import select
from pyrogram.types import Message

from core.logger import logger
from core.models import db_helper, User, State, Status


async def handle_message(message: Message):
    if message.text != 'тест':
        logger.debug(f'Получено сообщение {message.text} от пользователя {message.from_user.id}')
        return
    logger.info(f'Получено сообщение {message.text} от пользователя {message.from_user.id}')
    async with db_helper.session_factory() as session:
        # Проверяем, есть ли уже пользователь в базе данных
        user = await session.execute(select(User).where(User.id == message.from_user.id))
        user = user.scalars().first()

        if user is None:
            # Если пользователь не найден, добавляем его в базу данных
            new_user = User(
                id=message.from_user.id,
                state=State.new_user,
                status=Status.alive
            )
            session.add(new_user)
            await session.commit()
