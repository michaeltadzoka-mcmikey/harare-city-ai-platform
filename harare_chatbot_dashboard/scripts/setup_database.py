#!/usr/bin/env python
"""
Database setup script.
Run this once to create all tables.
"""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from dashboard.extensions import db

app = create_app()
with app.app_context():
    db.create_all()
    print("✅ Database tables created successfully.")