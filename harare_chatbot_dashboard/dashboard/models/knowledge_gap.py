from dashboard.extensions import db
from sqlalchemy import JSON
from datetime import datetime

class KnowledgeGap(db.Model):
    __tablename__ = 'knowledge_gaps'

    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    service = db.Column(db.String(50))
    service_risk = db.Column(db.String(20), default='medium')
    root_cause = db.Column(db.String(50))
    fallback_reason = db.Column(db.String(50))
    confidence = db.Column(db.Float)
    retrieval_result = db.Column(JSON)
    first_asked = db.Column(db.DateTime, server_default=db.func.now())
    last_asked = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    frequency = db.Column(db.Integer, default=1)
    recurrence_count = db.Column(db.Integer, default=0)
    base_priority = db.Column(db.Float)
    priority_score = db.Column(db.Float)
    impact = db.Column(db.String(20))
    status = db.Column(db.String(20), default='open')
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    draft_id = db.Column(db.Integer, db.ForeignKey('drafts.id'), nullable=True)
    suggested_documents = db.Column(JSON)
    resolution_type = db.Column(db.String(50))
    resolution_quality_score = db.Column(db.Float)
    resolved_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    notes = db.Column(db.Text)
    embedding = db.Column(JSON)

    assigned_user = db.relationship('User', foreign_keys=[assigned_to])
    resolved_by_user = db.relationship('User', foreign_keys=[resolved_by])

    def __repr__(self):
        return f'<KnowledgeGap {self.id} {self.question[:30]}>'