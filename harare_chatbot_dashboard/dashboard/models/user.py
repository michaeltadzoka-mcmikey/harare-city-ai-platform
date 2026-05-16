from dashboard.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import secrets


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120))
    password_hash = db.Column(db.String(200), nullable=False)
    department = db.Column(db.String(100))
    can_manage_users = db.Column(db.Boolean, default=False)
    can_manage_knowledge = db.Column(db.Boolean, default=False)
    active = db.Column(db.Boolean, default=True)
    password_change_required = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        self.password_change_required = True

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return self.active

    @staticmethod
    def generate_temp_password(length=12):
        return secrets.token_urlsafe(length)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'name': self.name or self.username,
            'department': self.department,
            'can_manage_users': self.can_manage_users,
            'can_manage_knowledge': self.can_manage_knowledge,
            'is_active': self.active,
            'password_change_required': self.password_change_required,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

    def get_flags(self):
        flags = []
        if self.can_manage_users:
            flags.append('Manage Users')
        if self.can_manage_knowledge:
            flags.append('Manage Knowledge')
        return flags

    def __repr__(self):
        return f'<User {self.username}>'
