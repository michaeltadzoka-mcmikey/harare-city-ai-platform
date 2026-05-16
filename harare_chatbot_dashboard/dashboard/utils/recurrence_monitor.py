# dashboard/utils/recurrence_monitor.py
from datetime import datetime, timedelta
from flask import current_app
from dashboard.extensions import db
from dashboard.models.knowledge_gap import KnowledgeGap

def check_gap_recurrence():
    """Detect gaps that have recurred after being marked completed."""
    fourteen_days_ago = datetime.utcnow() - timedelta(days=14)
    completed_gaps = KnowledgeGap.query.filter_by(status='completed').all()
    reopened = 0
    for gap in completed_gaps:
        similar = KnowledgeGap.query.filter(
            KnowledgeGap.status == 'open',
            KnowledgeGap.service == gap.service,
            KnowledgeGap.first_asked >= fourteen_days_ago,
            KnowledgeGap.question.ilike(f'%{gap.question[:20]}%')
        ).first()
        if similar:
            gap.status = 'open'
            gap.recurrence_count += 1
            if gap.resolution_quality_score:
                gap.resolution_quality_score *= 0.7
            db.session.add(gap)
            reopened += 1
    db.session.commit()
    return reopened