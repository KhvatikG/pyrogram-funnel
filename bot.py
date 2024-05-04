import asyncio

from pyrogram import Client, idle
from core.models import db_helper, Base
from message_handler import start_message_handler

from core.config import settings
from message_scheduler import send_scheduled_messages

app = Client(name='me_client', api_id=settings.API_ID, api_hash=settings.API_HASH)

async def main():
    # Инициализируем базу данных
    async with db_helper.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Вызываем функцию для добавления обработчика сообщений
    await start_message_handler(app)

    await asyncio.gather(
        asyncio.create_task(send_scheduled_messages(app)),
        app.run()
    )


if __name__ == '__main__':
    asyncio.run(main())
