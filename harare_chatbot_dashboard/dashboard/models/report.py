from dashboard.extensions import db
from datetime import datetime
from sqlalchemy import JSON

class Report(db.Model):
    __tablename__ = 'reports'

    id = db.Column(db.Integer, primary_key=True)
    reference_id = db.Column(db.String(50), unique=True, nullable=False)
    raw_text = db.Column(db.Text, nullable=False)
    raw_text_original = db.Column(db.Text)
    landmark = db.Column(db.String(200))
    standardized_type = db.Column(db.String(50))
    standardized_type_confidence = db.Column(db.Float)
    standardized_location = db.Column(db.String(100))
    standardized_location_confidence = db.Column(db.Float)
    urgency = db.Column(db.String(20), default='medium')
    duplicate_flag = db.Column(db.Boolean, default=False)
    duplicate_of = db.Column(db.String(50))
    spam_flag = db.Column(db.Boolean, default=False)
    spam_reason = db.Column(db.String(100))
    status = db.Column(db.String(20), default='submitted')
    assigned_department = db.Column(db.String(100))
    handled_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    internal_notes = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
    metadata_json = db.Column(JSON)

    # Relationship (string-based)
    handled_by_user = db.relationship('User', foreign_keys=[handled_by])

    def __repr__(self):
        return f'<Report {self.reference_id}>'