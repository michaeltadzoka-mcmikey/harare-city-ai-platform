from dashboard.extensions import db
from datetime import datetime
import hashlib

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    username = db.Column(db.String(80))
    action = db.Column(db.String(50), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.String(100))
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    note = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    # NEW: hash chain fields
    previous_hash = db.Column(db.String(64))
    hash = db.Column(db.String(64), unique=True)

    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<AuditLog {self.timestamp} {self.action}>'

    def compute_hash(self):
        """Compute SHA-256 hash of this record's data plus previous hash."""
        content = (
            f"{self.timestamp.isoformat() if self.timestamp else ''}"
            f"{self.user_id}{self.username}{self.action}{self.target_type}{self.target_id}"
            f"{self.old_value}{self.new_value}{self.note}{self.ip_address}"
            f"{self.previous_hash}"
        )
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def set_hash_chain(self):
        """Set previous_hash to the hash of the most recent log, then compute own hash."""
        last_log = AuditLog.query.order_by(AuditLog.id.desc()).first()
        self.previous_hash = last_log.hash if last_log else None
        self.hash = self.compute_hash()