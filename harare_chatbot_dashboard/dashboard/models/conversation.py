from dashboard.extensions import db
from sqlalchemy import JSON, Index

class Conversation(db.Model):
    __tablename__ = 'conversations'
    __table_args__ = (
        Index('idx_conversations_timestamp', 'timestamp'),
        Index('idx_conversations_service', 'service'),
        Index('idx_conversations_user_type', 'user_type'),
        Index('idx_conversations_session', 'session_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    user_type = db.Column(db.String(20), default='citizen')
    user_message = db.Column(db.Text, nullable=False)
    bot_response = db.Column(db.Text)
    intent = db.Column(db.String(100))
    confidence = db.Column(db.Float)
    source = db.Column(db.String(20))
    service = db.Column(db.String(50))
    metadata_json = db.Column(JSON)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

    # Relationship (string-based to avoid circular import)
    user = db.relationship('User', foreign_keys=[user_id])

    def get_metadata_field(self, field, default=None):
        """Safely extract a field from metadata_json."""
        if self.metadata_json and isinstance(self.metadata_json, dict):
            return self.metadata_json.get(field, default)
        return default

    def __repr__(self):
        return f'<Conversation {self.id} {self.user_message[:20]}>'