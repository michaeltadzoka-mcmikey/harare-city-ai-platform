from dashboard.extensions import db
from datetime import datetime
from sqlalchemy import JSON

class Escalation(db.Model):
    __tablename__ = 'escalations'

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True, nullable=False)
    query = db.Column(db.Text, nullable=False)
    session_id = db.Column(db.String(100))
    user_id = db.Column(db.String(100))
    reason = db.Column(db.String(200))
    status = db.Column(db.String(20), default='pending')
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)

    assignee = db.relationship('User', foreign_keys=[assigned_to])

    def __repr__(self):
        return f'<Escalation {self.reference}>'