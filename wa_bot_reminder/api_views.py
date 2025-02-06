from datetime import datetime, timedelta

import pytz
from flask import request, Response
from sqlalchemy import select

from . import app, db
from .crud import reminder_crud
from .models import Reminder, User
from .tasks import send_whatsapp_message


@app.route('/webhook', methods=['POST'])
def webhook():
    from_number = request.form.get('From')
    user = get_or_create_user(from_number, db.session)
    body = request.form.get('Body', '').strip()
    if not from_number or not body:
        return Response('Некорректные данные', status=400)
    parts = body.split(' ', 1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ''
    try:
        if command == '/set_timezone':
            user.tz = args.strip()
            db.session.commit()
            db.session.refresh(user)
            return Response(
                f'Установлен часовой пояс UTC{"+" + str(user.tz) if user.tz >= 0 else user.tz}',
                mimetype='text/plain'
            )
        elif command == 'список':
            reminders = reminder_crud.get_multi(user_number=user.phone_number, session=db.session)
            if reminders:
                response_message = 'Ваши напоминания:\n'
                for reminder in reminders:
                    response_message += (
                        f'ID: {reminder.id} | '
                        f'{reminder.reminder_time.strftime("%Y-%m-%d %H:%M:%S")} '
                        f'| {reminder.reminder_text}\n'
                    )
            else:
                response_message = 'У вас нет активных напоминаний.'
            return Response(response_message, mimetype='text/plain')
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
            now = datetime.utcnow().replace(tzinfo=pytz.utc)
            if remind_time <= now:
                return Response('Время должно быть в будущем!', mimetype='text/plain')
            reminder = Reminder(user_id=user.id, remind_time=remind_time, text=text)
            db.session.add(reminder)
            db.session.commit()
            send_whatsapp_message.apply_async(args=[from_number, text], eta=remind_time)
            return Response(
                f'Напоминание запланировано на '
                f'{(remind_time + timedelta(hours=user.tz)).strftime("%Y-%m-%d %H:%M")}',
                mimetype='text/plain'
            )
        if user.tz is None:
            return Response(
                'Установите ваш часовой пояс с помощью команды \n'
                '"/set_timezone <разница от UTC> "\n'
                'Пример: /set_timezone 3 (Москва)',
                mimetype='text/plain'
            )
        return Response(
            'Для добавления напоминания: напомни <ISO время>: <текст>\n'
            'Для получения списка: список\n'
            'Для удаления напоминания: удали <id>\n'
            'Для установки часового пояса: /set_timezone <разница от UTC>',
            mimetype='text/plain'
        )
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
