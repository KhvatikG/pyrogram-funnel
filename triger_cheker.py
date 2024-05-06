from core.config import settings

# Проверка на триггер пропуска сообщения
def check_skip_triggers(sent_messages):
    return any(word in message.text.lower() for message in sent_messages for word in settings.SKIP_TRIGGERS)

# Проверка на триггер окончания воронки
def check_final_triggers(sent_messages):
    return any(word in message.text.lower() for message in sent_messages for word in settings.FINAL_TRIGGERS)
