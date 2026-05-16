from dashboard.extensions import db
from datetime import datetime
from sqlalchemy import JSON

class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    version = db.Column(db.Integer, default=1)
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text)
    department = db.Column(db.String(100))
    owner_email = db.Column(db.String(120))
    valid_from = db.Column(db.Date, nullable=False)
    valid_to = db.Column(db.Date)
    locations = db.Column(JSON)  # list of suburbs or ["Council-wide"]
    authority_confidence = db.Column(db.Float, default=0.9)  # DEPRECATED – kept for backward compatibility only
    confidence_source = db.Column(db.String(200))
    content_type = db.Column(db.String(50))  # procedure, policy, fee_schedule, faq, emergency, contact_directory
    service_area = db.Column(db.String(50))  # from controlled vocabulary
    prerequisites = db.Column(JSON)  # list of strings (required items)
    related_documents = db.Column(JSON)  # list of document IDs
    # NEW FIELDS for RAG 2.2 compliance
    topic_tags = db.Column(JSON, nullable=False, default=[])          # mandatory array of keywords
    review_cycle = db.Column(db.String(50))                            # e.g., "quarterly", "annually"
    cross_service_flag = db.Column(db.Boolean, default=False)          # allow retrieval for other services
    authority_override = db.Column(JSON)                               # { "tier": "STATUTORY", "justification": "..." }

    status = db.Column(db.String(20), default='draft')  # draft, active, archived, expired, pending
    locked = db.Column(db.Boolean, default=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_modified_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    last_modified_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    ingested_at = db.Column(db.DateTime)
    needs_ingestion = db.Column(db.Boolean, default=True)

    # Relationships
    versions = db.relationship('DocumentVersion', backref='document', lazy='dynamic')
    uploaded_by_user = db.relationship('User', foreign_keys=[uploaded_by])
    last_modified_by_user = db.relationship('User', foreign_keys=[last_modified_by])

    def __repr__(self):
        return f'<Document {self.document_id} v{self.version}>'

class DocumentVersion(db.Model):
    __tablename__ = 'document_versions'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'))
    version = db.Column(db.Integer)
    content = db.Column(db.Text)
    metadata_json = db.Column(JSON)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.String(200))

    created_by_user = db.relationship('User', foreign_keys=[created_by])