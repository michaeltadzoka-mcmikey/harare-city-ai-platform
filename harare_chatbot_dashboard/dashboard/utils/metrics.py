"""
Metrics helper functions for Analytics module
"""
from datetime import datetime, timedelta
from dashboard.models import SessionLocal, Conversation, KnowledgeGap, Document, Override
from sqlalchemy import func

def compute_iii(start_date, end_date):
    """Compute Institutional Intelligence Index and components"""
    db = SessionLocal()
    try:
        # Coverage score (answered / total)
        total_convos = db.query(Conversation).filter(
            Conversation.timestamp.between(start_date, end_date)
        ).count()
        answered = db.query(Conversation).filter(
            Conversation.timestamp.between(start_date, end_date),
            Conversation.chatbot_response.isnot(None)
        ).count()
        coverage_score = (answered / total_convos * 100) if total_convos > 0 else 0

        # Knowledge health (100 - weighted open gaps impact)
        open_gaps = db.query(KnowledgeGap).filter(KnowledgeGap.status == 'open').all()
        total_impact = sum(g.priority_score for g in open_gaps)
        max_possible_impact = 100 * len(open_gaps) if open_gaps else 1
        knowledge_health = 100 - (total_impact / max_possible_impact * 100) if open_gaps else 100

        # Recurrence rate (recurring / resolved)
        resolved = db.query(KnowledgeGap).filter(
            KnowledgeGap.status == 'completed',
            KnowledgeGap.resolved_at.between(start_date, end_date)
        ).count()
        recurring = db.query(KnowledgeGap).filter(
            KnowledgeGap.recurrence_count > 0
        ).count()
        recurrence_rate = (recurring / resolved * 100) if resolved > 0 else 0

        # Override dependence ratio
        overrides = db.query(Override).filter(
            Override.created_at.between(start_date, end_date)
        ).count()
        override_dependence = (overrides / total_convos * 100) if total_convos > 0 else 0

        # Resolution quality average (from completed gaps)
        resolved_gaps = db.query(KnowledgeGap).filter(
            KnowledgeGap.status == 'completed'
        ).all()
        if resolved_gaps:
            avg_quality = sum(g.resolution_quality_score for g in resolved_gaps) / len(resolved_gaps)
        else:
            avg_quality = 100

        # Normalise components to 0-100
        iii = (
            coverage_score * 0.30 +
            knowledge_health * 0.25 +
            (100 - recurrence_rate) * 0.20 +
            avg_quality * 0.15 +
            (100 - override_dependence) * 0.10
        )
        iii = max(0, min(100, iii))

        components = {
            'coverage': round(coverage_score),
            'knowledge_health': round(knowledge_health),
            'recurrence': round(recurrence_rate),
            'override_dependence': round(override_dependence),
            'resolution_quality': round(avg_quality)
        }
        return round(iii), components
    finally:
        db.close()

def get_service_health(start_date, end_date):
    """Return list of service health cards data"""
    db = SessionLocal()
    try:
        # Get all distinct services from documents and conversations
        services = db.query(Document.service_area).distinct().all()
        services = [s[0] for s in services if s[0]]
        result = []
        for service in services:
            # Coverage for this service
            convos = db.query(Conversation).filter(
                Conversation.department == service,
                Conversation.timestamp.between(start_date, end_date)
            ).count()
            answered = db.query(Conversation).filter(
                Conversation.department == service,
                Conversation.timestamp.between(start_date, end_date),
                Conversation.chatbot_response.isnot(None)
            ).count()
            coverage = (answered / convos * 100) if convos > 0 else 0

            # Gaps for this service
            gaps = db.query(KnowledgeGap).filter(
                KnowledgeGap.service == service,
                KnowledgeGap.status == 'open'
            ).count()

            # Overrides affecting this service
            overrides = db.query(Override).filter(
                Override.service_area == service,
                Override.is_active == True
            ).count()

            result.append({
                'service': service,
                'score': round(coverage),
                'gaps': gaps,
                'overrides': overrides
            })
        return result
    finally:
        db.close()

def get_trend_data(days):
    """Return time‑series data for trend charts"""
    db = SessionLocal()
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        # Daily aggregation
        dates = [(start + timedelta(days=i)).date() for i in range(days)]
        labels = [d.strftime('%Y-%m-%d') for d in dates]

        # Conversation volume
        convos_by_day = db.query(
            func.date(Conversation.timestamp).label('date'),
            func.count().label('count')
        ).filter(
            Conversation.timestamp >= start
        ).group_by(func.date(Conversation.timestamp)).all()
        convos_dict = {str(row.date): row.count for row in convos_by_day}
        convos_data = [convos_dict.get(d, 0) for d in labels]

        # Gap creation
        gaps_by_day = db.query(
            func.date(KnowledgeGap.created_at).label('date'),
            func.count().label('count')
        ).filter(
            KnowledgeGap.created_at >= start
        ).group_by(func.date(KnowledgeGap.created_at)).all()
        gaps_dict = {str(row.date): row.count for row in gaps_by_day}
        gaps_data = [gaps_dict.get(d, 0) for d in labels]

        # For simplicity, return conversation and gap datasets
        return {
            'labels': labels,
            'datasets': [
                {
                    'label': 'Conversations',
                    'data': convos_data,
                    'borderColor': '#3498db',
                    'fill': false
                },
                {
                    'label': 'Gaps Created',
                    'data': gaps_data,
                    'borderColor': '#e74c3c',
                    'fill': false
                }
            ]
        }
    finally:
        db.close()

def get_expired_docs_count():
    """Return count of expired documents in active index"""
    db = SessionLocal()
    try:
        now = datetime.now()
        return db.query(Document).filter(
            Document.is_active == True,
            Document.valid_to < now
        ).count()
    finally:
        db.close()

def get_missing_validity_count():
    """Return count of documents missing validity dates"""
    db = SessionLocal()
    try:
        return db.query(Document).filter(
            Document.is_active == True,
            (Document.valid_from == None) | (Document.valid_to == None)
        ).count()
    finally:
        db.close()