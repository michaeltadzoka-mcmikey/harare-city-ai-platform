from dashboard.extensions import db
from datetime import datetime
from sqlalchemy import JSON

class ReviewQueue(db.Model):
    __tablename__ = 'review_queue'

    id = db.Column(db.Integer, primary_key=True)
    user_message = db.Column(db.Text, nullable=False)
    intent = db.Column(db.String(50))
    confidence = db.Column(db.Float)
    rag_response = db.Column(JSON)
    generated_answer = db.Column(db.Text)
    user_id = db.Column(db.String(100))
    session_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed = db.Column(db.Boolean, default=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_at = db.Column(db.DateTime)

    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

    def __repr__(self):
        return f'<ReviewQueue {self.id}>'