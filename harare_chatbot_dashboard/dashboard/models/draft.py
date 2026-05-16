from dashboard.extensions import db
from datetime import datetime

class Draft(db.Model):
    __tablename__ = 'drafts'

    id = db.Column(db.Integer, primary_key=True)
    gap_id = db.Column(db.Integer, db.ForeignKey('knowledge_gaps.id'), nullable=True)
    document_id = db.Column(db.String(100))
    content = db.Column(db.Text, nullable=False)
    metadata_json = db.Column(db.JSON)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    status = db.Column(db.String(20), default='draft')
    submitted_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    submitted_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_at = db.Column(db.DateTime)
    review_notes = db.Column(db.Text)

    gap = db.relationship('KnowledgeGap', foreign_keys=[gap_id])
    created_by_user = db.relationship('User', foreign_keys=[created_by])
    submitted_by_user = db.relationship('User', foreign_keys=[submitted_by])
    reviewed_by_user = db.relationship('User', foreign_keys=[reviewed_by])