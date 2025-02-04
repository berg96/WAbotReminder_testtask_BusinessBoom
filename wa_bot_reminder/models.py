from . import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String, nullable=False)
    tz = db.Column(db.Integer, nullable=True)

    reminders = db.relationship('Reminder', backref='user', lazy='select')


class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    remind_time = db.Column(db.DateTime, nullable=False)  # Дата и время напоминания
    text = db.Column(db.String, nullable=False)  # Текст напоминания
    is_recurring = db.Column(db.Boolean, default=False)  # Повторяющееся напоминание?
    recurrence = db.Column(db.String, nullable=True) # Тип повторения (daily, weekly)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
