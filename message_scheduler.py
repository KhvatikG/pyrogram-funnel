import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select, func

from core.config import settings
from core.models import db_helper, User, State, Status
from triger_cheker import check_skip_triggers, check_final_triggers


async def send_scheduled_messages(app):
    async with db_helper.session_factory() as session:
        while True:
            now = datetime.now()

            # Отправка message1 через 6 минут после первого сообщения пользователя
            six_minutes_ago = now - timedelta(minutes=6)
            users_for_message1 = await session.execute(
                select(User).where(
                    User.created_at < six_minutes_ago,
                    User.state == State.new_user,
                    User.status == Status.alive
                )
            )
            for user in users_for_message1.scalars():
                await process_user(
                    user=user,
                    session=session,
                    message_key='msg1',
                    app=app
                )

            # Отправка message2 через 39 минут после первого сообщения пользователя
            thirty_nine_minutes_ago = now - timedelta(minutes=39)
            users_for_message2 = await session.execute(
                select(User).where(
                    User.state_updated_at < thirty_nine_minutes_ago,
                    User.state == State.msg1_sent,
                    User.status == Status.alive
                )
            )
            for user in users_for_message2.scalars():
                await process_user(
                    user=user,
                    session=session,
                    message_key='msg2',
                    app=app,
                    check_skip=True
                )

            # Отправка message3 через 1 день 2 часа после отправки message2 или его отмены
            one_day_two_hours_ago = now - timedelta(days=1, hours=2)
            users_for_message3 = await session.execute(
                select(User).where(
                    (User.state == State.msg2_sent) | (User.state == State.msg2_skipped),
                    User.state_updated_at < one_day_two_hours_ago,
                    User.status == Status.alive
                )
            )
            for user in users_for_message3.scalars():
                await process_user(
                    user=user,
                    session=session,
                    message_key='msg3',
                    app=app
                )

            await asyncio.sleep(60)  # Проверять каждую минуту


async def process_user(user, session, message_key, app, check_skip=False):
    try:
        sent_messages = await app.get_history(user.user_id, limit=10)
        if check_skip and check_skip_triggers(sent_messages):
            user.state = State[f'{message_key}_skipped']
            user.state_updated_at = func.now()
            await session.commit()
            return
        if check_final_triggers(sent_messages):
            user.status = Status.finished
            user.status_updated_at = func.now()
            await session.commit()
            return

        await app.send_message(user.user_id, settings.TEXTS[message_key])
        user.state = State[f'{message_key}_sent']
        user.state_updated_at = func.now()
        await session.commit()
    except Exception:
        user.status = Status.dead
        user.status_updated_at = func.now()
        await session.commit()
