# dashboard/models/conflict.py
# New model for v3.2: track document conflicts and provisional resolutions

from dashboard.extensions import db
from datetime import datetime

class Conflict(db.Model):
    __tablename__ = 'conflicts'

    id = db.Column(db.Integer, primary_key=True)
    doc1_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    doc2_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)

    # Reason for conflict (e.g., 'overlap_validity', 'same_service_type')
    reason = db.Column(db.String(100), nullable=False)

    # Status: 'unresolved', 'provisionally_resolved', 'resolved'
    status = db.Column(db.String(20), default='unresolved', index=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_notified = db.Column(db.DateTime)  # for escalation reminders
    resolved_at = db.Column(db.DateTime)

    # If provisionally resolved, store the auto-resolution details
    provisional_decision = db.Column(db.JSON)  # { 'selected_doc_id': ..., 'justification': 'auto' }
    provisional_at = db.Column(db.DateTime)

    # When manually resolved
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    resolution_notes = db.Column(db.Text)

    # Relationships
    doc1 = db.relationship('Document', foreign_keys=[doc1_id])
    doc2 = db.relationship('Document', foreign_keys=[doc2_id])
    resolver = db.relationship('User', foreign_keys=[resolved_by])

    def __repr__(self):
        return f'<Conflict {self.doc1_id} vs {self.doc2_id}>'


class ProvisionalResolution(db.Model):
    __tablename__ = 'provisional_resolutions'

    id = db.Column(db.Integer, primary_key=True)
    conflict_id = db.Column(db.Integer, db.ForeignKey('conflicts.id'), nullable=False, unique=True)
    conflict = db.relationship('Conflict', backref=db.backref('provisional', uselist=False))

    # Auto-resolution details
    selected_doc_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    selected_doc = db.relationship('Document', foreign_keys=[selected_doc_id])
    justification = db.Column(db.String(200), default='Auto-resolved after 14 days')

    # Timestamp
    resolved_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Review status: 'pending', 'confirmed', 'overridden', 'reopened'
    review_status = db.Column(db.String(20), default='pending')
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_at = db.Column(db.DateTime)
    review_notes = db.Column(db.Text)

    # If overridden, link to new resolution (could be another conflict resolution)
    override_notes = db.Column(db.Text)

    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

    def __repr__(self):
        return f'<ProvisionalResolution conflict={self.conflict_id} status={self.review_status}>'