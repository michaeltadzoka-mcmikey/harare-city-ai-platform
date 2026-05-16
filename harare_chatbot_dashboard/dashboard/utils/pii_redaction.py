# dashboard/utils/pii_redactor.py
import re
from datetime import datetime, timedelta
from flask import current_app
from dashboard.extensions import db
from dashboard.models.report import Report
from dashboard.utils.encryption import encrypt

# Simple PII patterns (Zimbabwe-specific)
PII_PATTERNS = [
    (r'\b\d{10}\b', 'PHONE'),
    (r'\b\d{3}\s?\d{3}\s?\d{4}\b', 'PHONE'),
    (r'\b\d{2}-\d{7}[a-zA-Z]\d{2}\b', 'NATIONAL_ID'),
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'EMAIL'),
]

def redact_text(text):
    """Replace PII with [REDACTED] tags."""
    if not text:
        return text
    redacted = text
    for pattern, label in PII_PATTERNS:
        redacted = re.sub(pattern, f'[{label} REDACTED]', redacted)
    return redacted

def redact_pii(text):
    """Alias for redact_text."""
    return redact_text(text)

def redact_old_reports():
    """Find reports older than PII_REDACTION_DAYS and redact them."""
    days = current_app.config['PII_REDACTION_DAYS']
    cutoff = datetime.utcnow() - timedelta(days=days)
    reports = Report.query.filter(
        Report.submitted_at <= cutoff,
        Report.raw_text_original.is_(None)
    ).all()
    count = 0
    for report in reports:
        original = report.raw_text
        redacted = redact_text(original)
        if original != redacted:
            report.raw_text_original = encrypt(original)
            report.raw_text = redacted
            count += 1
    db.session.commit()
    return count