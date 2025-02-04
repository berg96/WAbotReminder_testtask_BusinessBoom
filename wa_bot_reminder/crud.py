from datetime import datetime

from sqlalchemy import select

from .import db
from .models import Reminder, User


class CRUDReminder:

    def get(self, obj_id, user_id, session):
        db_obj = session.execute(
            select(Reminder).where(
                Reminder.id == obj_id,
                Reminder.user_id == user_id
            )
        )
        return db_obj.scalars().first()

    def get_multi(self, user_number, session):
        user = session.execute(
            db.select(User).filter_by(phone_number=user_number)
        ).scalar_one_or_none()

        if user is None:
            return []  # Пользователь не найден

        upcoming_reminders = [
            reminder for reminder in user.reminders
            if reminder.remind_time >= datetime.utcnow()
        ]

        return upcoming_reminders

    def create(self, obj_in, session):
        obj_in_data = obj_in.dict()
        db_obj = Reminder(**obj_in_data)
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    # def update(self, db_obj, obj_in, session):
    #     obj_data = jsonable_encoder(db_obj)
    #     update_data = obj_in.dict(exclude_unset=True)
    #
    #     for field in obj_data:
    #         if field in update_data:
    #             setattr(db_obj, field, update_data[field])
    #     session.add(db_obj)
    #     session.commit()
    #     session.refresh(db_obj)
    #     return db_obj

    def remove(self, db_obj, session):
        session.delete(db_obj)
        session.commit()
        return db_obj

reminder_crud = CRUDReminder()
