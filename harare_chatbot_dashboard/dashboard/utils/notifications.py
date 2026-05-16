from dashboard.extensions import db
from dashboard.models.notification import Notification
from dashboard.models.user import User
from datetime import datetime, timedelta

def send_notification(user_ids=None, role_flag=None, title=None, message=None, link=None, expires_in_days=7):
    """
    Create a notification for specific users or all users with a given role flag.
    If user_ids is provided, role_flag is ignored.
    """
    if not user_ids and not role_flag:
        raise ValueError("Either user_ids or role_flag must be provided")
    
    if user_ids:
        for uid in user_ids:
            notif = Notification(
                user_id=uid,
                title=title,
                message=message,
                link=link,
                expires_at=datetime.utcnow() + timedelta(days=expires_in_days)
            )
            db.session.add(notif)
    elif role_flag:
        # Find all users with the given flag
        query = User.query
        if role_flag == 'manage_knowledge':
            query = query.filter_by(can_manage_knowledge=True)
        elif role_flag == 'both':
            query = query.filter_by(can_manage_knowledge=True, can_manage_users=True)
        else:
            raise ValueError(f"Unknown role flag: {role_flag}")
        users = query.all()
        for user in users:
            notif = Notification(
                user_id=user.id,
                title=title,
                message=message,
                link=link,
                expires_at=datetime.utcnow() + timedelta(days=expires_in_days)
            )
            db.session.add(notif)
    db.session.commit()