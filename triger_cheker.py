from core.config import settings


def check_skip_triggers(sent_messages):
    return any(word in message.text.lower() for message in sent_messages for word in settings.SKIP_TRIGGERS)


def check_final_triggers(sent_messages):
    return any(word in message.text.lower() for message in sent_messages for word in settings.FINAL_TRIGGERS)
