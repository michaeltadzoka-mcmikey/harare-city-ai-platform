from dashboard.extensions import db
from datetime import datetime
from sqlalchemy import JSON

class Override(db.Model):
    __tablename__ = 'overrides'

    id = db.Column(db.Integer, primary_key=True)
    override_id = db.Column(db.String(50), unique=True)
    override_type = db.Column(db.String(50), nullable=False)
    target_type = db.Column(db.String(20))
    target_value = db.Column(db.String(200))
    service = db.Column(db.String(50))
    location_scope = db.Column(JSON)
    trigger_conditions = db.Column(JSON)
    content = db.Column(db.Text)
    valid_from = db.Column(db.Date, default=datetime.utcnow().date)
    valid_to = db.Column(db.Date)
    justification = db.Column(db.Text)
    approved = db.Column(db.Boolean, default=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    revoked_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    revoked_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)

    created_by_user = db.relationship('User', foreign_keys=[created_by])
    approved_by_user = db.relationship('User', foreign_keys=[approved_by])
    revoked_by_user = db.relationship('User', foreign_keys=[revoked_by])

    def __repr__(self):
        return f'<Override {self.override_id} {self.override_type}>'