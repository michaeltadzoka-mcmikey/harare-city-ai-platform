from dashboard.extensions import db
from datetime import datetime

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # null = broadcast to all with specific flag
    role_flag = db.Column(db.String(20))  # 'manage_knowledge', 'both', etc. – for targeting
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(200))  # optional URL to related page
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)  # optional

    def __repr__(self):
        return f'<Notification {self.id} {self.title}>'