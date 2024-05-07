import asyncio

from pyrogram import Client, filters
from pyrogram.types import Message
from core.models import db_helper, Base
from message_handler import handle_message

from core.config import settings
from message_scheduler import send_scheduled_messages


async def start_handler(client: Client):
    @client.on_message(filters=filters.private)
    async def handler_(_, message: Message):
        await handle_message(message)


async def main():
    app = Client(name='me_client', api_id=settings.API_ID, api_hash=settings.API_HASH)

    # Инициализируем базу данных
    async with db_helper.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await app.start()
    await start_handler(app)
    await send_scheduled_messages(app)
    await app.stop()


if __name__ == '__main__':
    asyncio.run(main())
