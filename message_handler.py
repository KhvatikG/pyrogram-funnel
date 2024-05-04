from pyrogram import filters
from sqlalchemy import select

from core.models import db_helper, User, State, Status


async def handle_message(message):
    async with db_helper.session_factory() as session:
        # Проверяем, есть ли уже пользователь в базе данных
        user = await session.execute(select(User).where(User.id == message.from_user.id))
        user = user.scalars().first()

        if user is None:
            # Если пользователь не найден, добавляем его в базу данных
            new_user = User(
                user_id=message.from_user.id,
                state=State.new_user,
                status=Status.alive
            )
            session.add(new_user)
            await session.commit()


async def start_message_handler(app):
    app.add_handler(filters.private & filters.incoming)(handle_message)
