from dashboard.extensions import db
from datetime import datetime


class SpamKeyword(db.Model):
    __tablename__ = 'spam_keywords'

    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<SpamKeyword {self.keyword}>'