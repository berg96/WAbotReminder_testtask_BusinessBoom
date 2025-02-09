from datetime import datetime, timedelta

import pytz
from flask import request, Response
from sqlalchemy import select
from twilio.twiml.messaging_response import MessagingResponse

from settings import Config
from . import app, db, client
from .crud import reminder_crud
from .models import Reminder, User
from .tasks import send_whatsapp_message


import logging

logging.basicConfig(
    level=logging.INFO,  # или DEBUG для более подробного логирования
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
)

logger = logging.getLogger(__name__)


@app.route('/webhook', methods=['POST'])
def webhook():
    from_number = request.form.get('From')
    user = get_or_create_user(from_number, db.session)
    body = request.form.get('Body', '').strip()
    response = MessagingResponse()
    if not from_number or not body:
        return Response('Некорректные данные', status=400)
    parts = body.split(' ', 1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ''
    try:
        if command == '/set_timezone':
            user.tz = int(args.strip())
            db.session.commit()
            db.session.refresh(user)
            response.message(f'Установлен часовой пояс UTC{"+" + str(user.tz) if user.tz >= 0 else user.tz}')
            return str(response), 200, {'Content-Type': 'application/xml'}
        elif command == 'список':
            logger.info('зашел в список')
            reminders = reminder_crud.get_multi(user_number=user.phone_number, session=db.session)
            logger.info('собрал данные')
            logger.info(f'{reminders is not None}')
            logger.info(f'{reminders}')

            if reminders:
                response_message = 'Ваши напоминания:\n'
                logger.info(f'response_message: {response_message}')

                for reminder in reminders:
                    logger.info(f'id: {reminder.id}')
                    logger.info(f'время: {reminder.remind_time.strftime("%Y-%m-%d %H:%M:%S")}')
                    logger.info(f'текст: {reminder.text}')

                    response_message += (
                        f'ID: {reminder.id} | '
                        f'{(reminder.remind_time + timedelta(hours=user.tz)).strftime("%Y-%m-%d %H:%M:%S")} '
                        f'| {reminder.text}\n'
                    )
                    logger.info(f'response_message: {response_message}')

            else:
                response_message = 'У вас нет активных напоминаний.'
            logger.info(f'Перед отправкой')
            logger.info(f'response_message: {response_message[:-1]}')
            # return Response(response_message, mimetype='text/plain')
            response.message(response_message)
            return str(response), 200, {'Content-Type': 'application/xml'}
        elif command == 'удали':
            reminder = reminder_crud.get(
                obj_id=args.strip(), user_id=user.id, session=db.session
            )
            if reminder is None:
                return Response('Напоминание не найдено', mimetype='text/plain')
            reminder_crud.remove(reminder, db.session)
            return Response('Напоминание удалено', mimetype='text/plain')
        elif command == 'напомни':
            if ";" not in args:
                return Response(
                    'Неверный формат.'
                    ' Пример: "напомни 2025-02-04 14:30; Ваш текст"',
                    mimetype='text/plain'
                )
            time_str, text = args.split(";", 1)
            text = text.strip()
            from dateutil import parser
            local_dt = parser.parse(time_str.strip())
            remind_time = local_dt - timedelta(hours=user.tz)
            now = datetime.utcnow()
            if remind_time <= now:
                return Response('Время должно быть в будущем!', mimetype='text/plain')
            reminder = Reminder(user_id=user.id, remind_time=remind_time, text=text)
            logger.info('создал запись1')
            db.session.add(reminder)
            db.session.commit()
            db.session.refresh(reminder)
            logger.info('обновил запись')
            send_whatsapp_message.apply_async(args=[from_number, text], eta=remind_time)
            # return Response(
            #     f'Напоминание запланировано на '
            #     f'{(remind_time + timedelta(hours=user.tz)).strftime("%Y-%m-%d %H:%M")}',
            #     mimetype='text/plain'
            # )

            response.message(
                f'Напоминание запланировано на '
                f'{(remind_time + timedelta(hours=user.tz)).strftime("%Y-%m-%d %H:%M")}'
            )
            return str(response), 200, {'Content-Type': 'application/xml'}

        if user.tz is None:
            msg = (
                'Установите ваш часовой пояс с помощью команды \n'
                '"/set_timezone <разница от UTC> "\n'
                'Пример: /set_timezone 3 (Москва)',
            )
            # return Response(
            #     'Установите ваш часовой пояс с помощью команды \n'
            #     '"/set_timezone <разница от UTC> "\n'
            #     'Пример: /set_timezone 3 (Москва)',
            #     mimetype='text/plain'
            # )
            send_whatsapp_message(user.phone_number, msg)
        # return Response(
        #     'Для добавления напоминания: напомни <ISO время>: <текст>\n'
        #     'Для получения списка: список\n'
        #     'Для удаления напоминания: удали <id>\n'
        #     'Для установки часового пояса: /set_timezone <разница от UTC>',
        #     mimetype='text/plain'
        # )
        msg = (
            'Для добавления напоминания: напомни <ISO время>: <текст>\n'
            'Для получения списка: список\n'
            'Для удаления напоминания: удали <id>\n'
            'Для установки часового пояса: /set_timezone <разница от UTC>'
        )
        # response.message(
        #     'Для добавления напоминания: напомни <ISO время>: <текст>\n'
        #     'Для получения списка: список\n'
        #     'Для удаления напоминания: удали <id>\n'
        #     'Для установки часового пояса: /set_timezone <разница от UTC>'
        # )
        # return str(response), 200, {'Content-Type': 'application/xml'}
        return send_whatsapp_message(user.phone_number, msg)
    except Exception as e:
        db.session.rollback()
        return Response(f'Внутренняя ошибка сервера: {e}', status=500)


def get_or_create_user(phone_number, session):
    user = session.execute(select(User).where(
        User.phone_number == phone_number
    )).scalars().first()
    if user is None:
        user = User(phone_number=phone_number)
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


def send_whatsapp_message(to_number, message_body):
    try:
        message = client.messages.create(
            body=message_body,
            from_=Config.TWILIO_WHATSAPP_NUMBER,  # номер отправителя из WhatsApp Sandbox или вашего аккаунта
            to=f'whatsapp:{to_number}'       # номер получателя в формате "whatsapp:+<номер>"
        )
        print(f"Message sent, SID: {message.sid}")
        return message.sid
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")
        return None
