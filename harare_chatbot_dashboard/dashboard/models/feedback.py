from dashboard.extensions import db
from datetime import datetime

class CitizenFeedback(db.Model):
    __tablename__ = 'citizen_feedback'

    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.String(100))
    feedback_type = db.Column(db.String(50))  # incorrect, missing, outdated
    details = db.Column(db.Text)
    session_id = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='new')