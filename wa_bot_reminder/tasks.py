from . import celery, client
from settings import Config


@celery.task
def send_whatsapp_message(user_number, message):
    """Отправка WhatsApp-сообщения"""
    try:
        client.messages.create(
            body=message,
            from_=Config.TWILIO_WHATSAPP_NUMBER,
            to=user_number
        )
        print(f"Отправлено: {user_number} -> {message}")
    except Exception as e:
        print(f"Ошибка отправки на {user_number}: {e}")
