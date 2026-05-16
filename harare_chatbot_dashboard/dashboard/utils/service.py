from dashboard.extensions import db
from datetime import datetime

class Service(db.Model):
    __tablename__ = 'services'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)          # e.g., "water"
    display_name = db.Column(db.String(100))                              # e.g., "Water & Sanitation"
    description = db.Column(db.Text)
    tags = db.Column(db.JSON, default=[])
    required_content_types = db.Column(db.JSON, nullable=False)           # list of required categories
    location_requirements = db.Column(db.JSON, default={})                # future: ward/suburb coverage
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Service {self.name}>'