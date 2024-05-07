from core.config import settings


# Проверка на триггер пропуска сообщения
async def check_skip_triggers(sent_messages):
    async for message in sent_messages:
        for word in settings.SKIP_TRIGGERS:
            if word.lower() in message.text.lower():
                return True
    return False


# Проверка на триггер окончания воронки
async def check_final_triggers(sent_messages):
    async for message in sent_messages:
        for word in settings.FINAL_TRIGGERS:
            if word.lower() in message.text.lower():
                return True
    return False
