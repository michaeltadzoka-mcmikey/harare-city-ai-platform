from dashboard.models.document import Document
from dashboard.models.service import Service
from dashboard.models.override import Override
from sqlalchemy import func
from datetime import date

def get_service_coverage_scores():
    """
    Compute Service Coverage Score (SCS) for all services.
    Returns list of dicts: service name, coverage %, missing categories, conflict penalty, expired penalty, health score.
    """
    services = Service.query.all()
    result = []
    for svc in services:
        # Count active documents per required content type
        active_counts = {}
        for ct in svc.required_content_types:
            count = Document.query.filter_by(
                service_area=svc.name,
                content_type=ct,
                status='active'
            ).count()
            active_counts[ct] = count

        # Weighted coverage (weights defined in config or per service)
        # For simplicity, equal weight per category.
        total_weight = len(svc.required_content_types)
        present_weight = sum(1 for ct in svc.required_content_types if active_counts.get(ct, 0) > 0)
        coverage_raw = (present_weight / total_weight) * 100 if total_weight else 0

        # Expired penalty: (expired docs in this service) / (total ever authored)
        expired_count = Document.query.filter_by(
            service_area=svc.name,
            status='archived'
        ).count()
        total_authored = Document.query.filter_by(service_area=svc.name).count()
        expired_penalty = expired_count / max(1, total_authored) if total_authored else 0

        # Conflict penalty: count unresolved conflicts (simplified: any overlap among active same-type docs)
        # We'll use a placeholder; ideally need conflict detection from RAG.
        conflict_count = 0  # fetch from RAG or local
        conflict_penalty = conflict_count / max(1, total_authored) if total_authored else 0

        # Health score
        health_score = coverage_raw * 0.5 - conflict_penalty * 30 - expired_penalty * 20
        health_score = max(0, min(100, health_score))  # clamp

        missing = [ct for ct in svc.required_content_types if active_counts.get(ct, 0) == 0]

        result.append({
            'name': svc.name,
            'display_name': svc.display_name or svc.name,
            'coverage': round(coverage_raw, 1),
            'missing_categories': missing,
            'conflict_penalty': round(conflict_penalty * 100, 1),
            'expired_penalty': round(expired_penalty * 100, 1),
            'health_score': round(health_score, 1)
        })
    return result