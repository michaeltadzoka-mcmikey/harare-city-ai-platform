from flask import Blueprint, render_template, request, jsonify, current_app, Response
from flask_login import login_required
from dashboard.extensions import db, cache
from dashboard.models.conversation import Conversation
from dashboard.models.document import Document
from dashboard.models.knowledge_gap import KnowledgeGap
from dashboard.models.report import Report
from dashboard.models.override import Override
from dashboard.models.review_queue import ReviewQueue
from dashboard.models.service import Service  # <-- import Service model
from dashboard.utils.rag_client import get_rag_status
from dashboard.utils.llm_client import get_llm_status
from dashboard.utils.rasa_client import get_rasa_status
from dashboard.decorators import manage_knowledge_required
from datetime import datetime, timedelta, date
from sqlalchemy import func, and_, or_
import logging
import time
import csv
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

bp = Blueprint('analytics', __name__, url_prefix='/analytics')


def get_all_services():
    """
    Return a list of all service names that should be considered in analytics.
    Includes:
    - All active services from the Service table (if exists)
    - Plus any distinct service_area from Document table (to catch legacy or unregistered services)
    Returns a sorted list of unique service names.
    """
    service_set = set()
    try:
        # Get from Service model
        services_from_model = db.session.query(Service.name).filter(Service.is_active == True).all()
        for s in services_from_model:
            service_set.add(s[0])
    except Exception as e:
        logger.warning(f"Could not query Service table: {e}")
    
    # Get from Document.service_area (non‑null, non‑empty)
    try:
        doc_services = db.session.query(Document.service_area).distinct().filter(Document.service_area.isnot(None)).all()
        for s in doc_services:
            if s[0] and s[0].strip():
                service_set.add(s[0])
    except Exception as e:
        logger.warning(f"Could not query Document service areas: {e}")
    
    # Fallback: if still empty, return a default list (should not happen in production)
    if not service_set:
        logger.warning("No services found in database; using empty list.")
        return []
    
    return sorted(list(service_set))


def fetch_health_status():
    """Fetch health status of external services (no app context needed)"""
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(get_rag_status): 'rag',
            executor.submit(get_llm_status): 'llm',
            executor.submit(get_rasa_status): 'rasa'
        }
        results = {'rag': {}, 'llm': {}, 'rasa': {}}
        for future in as_completed(futures):
            service = futures[future]
            try:
                results[service] = future.result()
            except Exception as e:
                logger.error(f"Health check failed for {service}: {e}")
                results[service] = {'status': 'offline'}
        return results


def get_period_dates(period):
    end_date = datetime.utcnow().date()
    if period == '7d':
        start_date = end_date - timedelta(days=7)
    elif period == '30d':
        start_date = end_date - timedelta(days=30)
    elif period == '90d':
        start_date = end_date - timedelta(days=90)
    else:
        start_date = end_date - timedelta(days=30)
    return start_date, end_date


@bp.route('/')
@login_required
def index():
    return render_template('analytics.html')


@bp.route('/api/data')
@login_required
def get_analytics_data():
    start_total = time.time()
    period = request.args.get('period', '30d')
    compare = request.args.get('compare', 'none')

    start_date, end_date = get_period_dates(period)

    if compare == 'previous':
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - (end_date - start_date)
    else:
        prev_start = prev_end = None

    health_results = fetch_health_status()
    rag_online = health_results['rag'].get('status') == 'healthy'

    # Helper to run a task with application context
    def run_with_context(task, *args, **kwargs):
        with current_app.app_context():
            return task(*args, **kwargs)

    try:
        trends = get_trends(start_date, end_date)
        logger.info(f"Trends conversation_volume length: {len(trends['conversation_volume'])}")
    except Exception as e:
        logger.error(f"Error in get_trends: {e}", exc_info=True)
        trends = {'conversation_volume': [], 'gap_creation': [], 'override_usage': [],
                  'expiry_trends': [], 'pinned_usage': [], 'service_performance': {}}

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(run_with_context, calculate_iii_and_components, start_date, end_date): 'iii',
            executor.submit(run_with_context, get_risk_stability, start_date, end_date, rag_online): 'risk',
            executor.submit(run_with_context, get_service_health, start_date, end_date, rag_online): 'service_health',
            executor.submit(run_with_context, get_reports_overview, start_date, end_date): 'reports'
        }
        if compare == 'previous':
            futures[executor.submit(run_with_context, calculate_iii_and_components, prev_start, prev_end)] = 'iii_prev'

        results = {}
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                logger.error(f"Analytics subtask {key} failed: {e}", exc_info=True)
                if key == 'iii' or key == 'iii_prev':
                    results[key] = {'iii': 0, 'components': {}}
                elif key == 'risk':
                    results[key] = {'open_gaps': 0, 'high_risk_gaps': 0, 'recurring_gaps': 0,
                                    'override_triggers': 0, 'avg_resolution_days': 0,
                                    'expired_docs': 0, 'missing_validity': 0, 'pinned_overrides': 0}
                elif key == 'service_health':
                    results[key] = []
                elif key == 'reports':
                    results[key] = {'submitted': 0, 'in_progress': 0, 'resolved': 0,
                                    'avg_resolution_days': 0, 'distribution': []}
                else:
                    results[key] = {}

    total_time = time.time() - start_total
    logger.info(f"Analytics API total time: {total_time:.3f}s")

    data = {
        'iii': results['iii']['iii'],
        'iii_components': results['iii']['components'],
        'risk_stability': results['risk'],
        'trends': trends,
        'service_health': results['service_health'],
        'reports_overview': results['reports']
    }
    if compare == 'previous':
        data['comparison'] = {
            'iii_prev': results['iii_prev']['iii'],
            'trends_prev': get_trends(prev_start, prev_end)
        }
    return jsonify(data)


def calculate_iii_and_components(start_date, end_date):
    """Return III score and its five component values."""
    try:
        total_convs = db.session.query(func.count(Conversation.id)).filter(
            func.date(Conversation.timestamp) >= start_date,
            func.date(Conversation.timestamp) <= end_date
        ).scalar() or 0
        answered_convs = db.session.query(func.count(Conversation.id)).filter(
            func.date(Conversation.timestamp) >= start_date,
            func.date(Conversation.timestamp) <= end_date,
            Conversation.source != 'fallback'
        ).scalar() or 0
        coverage = (answered_convs / total_convs * 100) if total_convs else 100
    except Exception as e:
        logger.error(f"Coverage calculation failed: {e}")
        coverage = 0

    try:
        open_gaps = KnowledgeGap.query.filter_by(status='open').all()
        total_impact = sum(g.priority_score or 0 for g in open_gaps)
        max_possible = len(open_gaps) * 100 if open_gaps else 1
        knowledge_health = 100 - (total_impact / max_possible * 100) if max_possible else 100
    except Exception as e:
        logger.error(f"Knowledge health calculation failed: {e}")
        knowledge_health = 0

    try:
        resolved = db.session.query(func.count(KnowledgeGap.id)).filter(
            KnowledgeGap.status == 'completed',
            func.date(KnowledgeGap.resolved_at) >= start_date,
            func.date(KnowledgeGap.resolved_at) <= end_date
        ).scalar() or 0
        recurring = db.session.query(func.count(KnowledgeGap.id)).filter(
            KnowledgeGap.recurrence_count > 0,
            func.date(KnowledgeGap.resolved_at) >= start_date,
            func.date(KnowledgeGap.resolved_at) <= end_date
        ).scalar() or 0
        recurrence_rate = (recurring / resolved * 100) if resolved else 0
    except Exception as e:
        logger.error(f"Recurrence rate calculation failed: {e}")
        recurrence_rate = 0

    try:
        quality = db.session.query(func.avg(KnowledgeGap.resolution_quality_score)).filter(
            func.date(KnowledgeGap.resolved_at) >= start_date,
            func.date(KnowledgeGap.resolved_at) <= end_date
        ).scalar() or 70
    except Exception as e:
        logger.error(f"Resolution quality calculation failed: {e}")
        quality = 70

    try:
        overrides = db.session.query(func.count(Override.id)).filter(
            func.date(Override.created_at) >= start_date,
            func.date(Override.created_at) <= end_date
        ).scalar() or 0
        override_dependence = (overrides / total_convs * 100) if total_convs else 0
    except Exception as e:
        logger.error(f"Override dependence calculation failed: {e}")
        override_dependence = 0

    iii = (
        coverage * current_app.config.get('III_COVERAGE_WEIGHT', 0.30) +
        knowledge_health * current_app.config.get('III_KNOWLEDGE_HEALTH_WEIGHT', 0.25) +
        (100 - recurrence_rate) * current_app.config.get('III_RECURRENCE_WEIGHT', 0.20) +
        quality * current_app.config.get('III_RESOLUTION_QUALITY_WEIGHT', 0.15) +
        (100 - min(override_dependence, 100)) * current_app.config.get('III_OVERRIDE_DEPENDENCE_WEIGHT', 0.10)
    )

    return {
        'iii': round(iii, 1),
        'components': {
            'coverage': round(coverage, 1),
            'knowledge_health': round(knowledge_health, 1),
            'recurrence': round(recurrence_rate, 1),
            'resolution_quality': round(quality, 1),
            'override_dependence': round(override_dependence, 1)
        }
    }


def get_risk_stability(start_date, end_date, rag_online=True):
    try:
        open_gaps = KnowledgeGap.query.filter_by(status='open').count()
        high_risk = KnowledgeGap.query.filter(
            KnowledgeGap.priority_score >= 80,
            KnowledgeGap.status == 'open'
        ).count()
        recurring = KnowledgeGap.query.filter(
            KnowledgeGap.recurrence_count > 0).count()
        override_triggers = db.session.query(func.count(Override.id)).filter(
            func.date(Override.created_at) >= start_date,
            func.date(Override.created_at) <= end_date
        ).scalar() or 0
        avg_resolution = db.session.query(
            func.avg(func.julianday(KnowledgeGap.resolved_at) -
                     func.julianday(KnowledgeGap.first_asked))
        ).filter(KnowledgeGap.resolved_at.isnot(None)).scalar() or 0
    except Exception as e:
        logger.error(f"Risk stability calculation failed: {e}")
        open_gaps = high_risk = recurring = override_triggers = 0
        avg_resolution = 0

    try:
        today = datetime.utcnow().date()
        doc_query = Document.query.filter(Document.valid_to < today)
        if hasattr(Document, 'is_active'):
            doc_query = doc_query.filter(Document.is_active == True)
        elif hasattr(Document, 'status'):
            doc_query = doc_query.filter(Document.status == 'active')
        expired_docs = doc_query.count()
    except Exception as e:
        logger.error(f"Expired docs calculation failed: {e}")
        expired_docs = 0

    try:
        missing_query = Document.query.filter(
            or_(Document.valid_from.is_(None), Document.valid_to.is_(None))
        )
        if hasattr(Document, 'is_active'):
            missing_query = missing_query.filter(Document.is_active == True)
        elif hasattr(Document, 'status'):
            missing_query = missing_query.filter(Document.status == 'active')
        missing_validity = missing_query.count()
    except Exception as e:
        logger.error(f"Missing validity calculation failed: {e}")
        missing_validity = 0

    try:
        pinned_overrides = Override.query.filter_by(
            override_type='pinned', is_active=True).count()
    except Exception as e:
        logger.error(f"Pinned overrides calculation failed: {e}")
        pinned_overrides = 0

    return {
        'open_gaps': open_gaps,
        'high_risk_gaps': high_risk,
        'recurring_gaps': recurring,
        'override_triggers': override_triggers,
        'avg_resolution_days': round(avg_resolution, 1),
        'expired_docs': expired_docs,
        'missing_validity': missing_validity,
        'pinned_overrides': pinned_overrides
    }


def get_trends(start_date, end_date):
    days = (end_date - start_date).days + 1
    date_range = [start_date + timedelta(days=i) for i in range(days)]

    # Conversation volume – use date‑only filter
    try:
        conv_trend = db.session.query(
            func.date(Conversation.timestamp).label('date'),
            func.count().label('count')
        ).filter(
            func.date(Conversation.timestamp) >= start_date,
            func.date(Conversation.timestamp) <= end_date
        ).group_by(func.date(Conversation.timestamp)).all()
        conv_dict = {row.date: row.count for row in conv_trend}
    except Exception as e:
        logger.error(f"Conversation volume trend failed: {e}")
        conv_dict = {}
    conv_volume = [{'date': d.isoformat(), 'count': conv_dict.get(d.isoformat(), 0)} for d in date_range]

    # Gap creation
    try:
        gap_trend = db.session.query(
            func.date(KnowledgeGap.first_asked).label('date'),
            func.count().label('count')
        ).filter(
            func.date(KnowledgeGap.first_asked) >= start_date,
            func.date(KnowledgeGap.first_asked) <= end_date
        ).group_by(func.date(KnowledgeGap.first_asked)).all()
        gap_dict = {row.date: row.count for row in gap_trend}
    except Exception as e:
        logger.error(f"Gap creation trend failed: {e}")
        gap_dict = {}
    gap_creation = [{'date': d.isoformat(), 'count': gap_dict.get(d.isoformat(), 0)} for d in date_range]

    # Override usage
    try:
        override_trend = db.session.query(
            func.date(Override.created_at).label('date'),
            func.count().label('count')
        ).filter(
            func.date(Override.created_at) >= start_date,
            func.date(Override.created_at) <= end_date
        ).group_by(func.date(Override.created_at)).all()
        override_dict = {row.date: row.count for row in override_trend}
    except Exception as e:
        logger.error(f"Override usage trend failed: {e}")
        override_dict = {}
    override_usage = [{'date': d.isoformat(), 'count': override_dict.get(d.isoformat(), 0)} for d in date_range]

    # Expiry trends (Document.valid_to is a date)
    expiry_trend = []
    for d in date_range:
        try:
            doc_q = Document.query.filter(Document.valid_to == d)
            if hasattr(Document, 'is_active'):
                doc_q = doc_q.filter(Document.is_active == True)
            elif hasattr(Document, 'status'):
                doc_q = doc_q.filter(Document.status == 'active')
            count = doc_q.count()
        except Exception as e:
            logger.error(f"Expiry trend for {d} failed: {e}")
            count = 0
        expiry_trend.append({'date': d.isoformat(), 'count': count})

    # Pinned usage
    try:
        pinned_trend = db.session.query(
            func.date(Override.created_at).label('date'),
            func.count().label('count')
        ).filter(
            func.date(Override.created_at) >= start_date,
            func.date(Override.created_at) <= end_date,
            Override.override_type == 'pinned'
        ).group_by(func.date(Override.created_at)).all()
        pinned_dict = {row.date: row.count for row in pinned_trend}
    except Exception as e:
        logger.error(f"Pinned usage trend failed: {e}")
        pinned_dict = {}
    pinned_usage = [{'date': d.isoformat(), 'count': pinned_dict.get(d.isoformat(), 0)} for d in date_range]

    # Service performance over time – use dynamic service list
    services = get_all_services()
    service_perf = {}
    for service in services:
        service_perf[service] = []
        for d in date_range:
            try:
                total = Conversation.query.filter(
                    func.date(Conversation.timestamp) == d,
                    Conversation.service == service
                ).count()
                answered = Conversation.query.filter(
                    func.date(Conversation.timestamp) == d,
                    Conversation.service == service,
                    Conversation.source != 'fallback'
                ).count()
                success = round((answered / total * 100) if total else 100)
            except Exception as e:
                logger.error(f"Service performance for {service} on {d} failed: {e}")
                success = 100
            service_perf[service].append({'date': d.isoformat(), 'success': success})

    return {
        'conversation_volume': conv_volume,
        'gap_creation': gap_creation,
        'override_usage': override_usage,
        'expiry_trends': expiry_trend,
        'pinned_usage': pinned_usage,
        'service_performance': service_perf
    }


def get_service_health(start_date, end_date, rag_online=True):
    services = get_all_services()
    today = datetime.utcnow().date()
    result = []
    for service in services:
        try:
            total = Conversation.query.filter(
                func.date(Conversation.timestamp) >= start_date,
                func.date(Conversation.timestamp) <= end_date,
                Conversation.service == service
            ).count()
            answered = Conversation.query.filter(
                func.date(Conversation.timestamp) >= start_date,
                func.date(Conversation.timestamp) <= end_date,
                Conversation.service == service,
                Conversation.source != 'fallback'
            ).count()
            coverage = round((answered / total * 100) if total else 100)
        except Exception as e:
            logger.error(f"Service health coverage for {service} failed: {e}")
            coverage = 0

        try:
            gaps = KnowledgeGap.query.filter_by(
                service=service, status='open').count()
            critical_gaps = KnowledgeGap.query.filter(
                KnowledgeGap.service == service,
                KnowledgeGap.status == 'open',
                KnowledgeGap.priority_score >= 80
            ).count()
        except Exception as e:
            logger.error(f"Service health gaps for {service} failed: {e}")
            gaps = critical_gaps = 0

        try:
            overrides = Override.query.filter_by(
                service=service, is_active=True).count()
        except Exception as e:
            logger.error(f"Service health overrides for {service} failed: {e}")
            overrides = 0

        try:
            doc_q = Document.query.filter(
                Document.service_area == service,
                Document.valid_to < today
            )
            if hasattr(Document, 'is_active'):
                doc_q = doc_q.filter(Document.is_active == True)
            elif hasattr(Document, 'status'):
                doc_q = doc_q.filter(Document.status == 'active')
            expired = doc_q.count()
        except Exception as e:
            logger.error(f"Service health expired docs for {service} failed: {e}")
            expired = 0

        try:
            missing_q = Document.query.filter(
                Document.service_area == service,
                or_(Document.valid_from.is_(None), Document.valid_to.is_(None))
            )
            if hasattr(Document, 'is_active'):
                missing_q = missing_q.filter(Document.is_active == True)
            elif hasattr(Document, 'status'):
                missing_q = missing_q.filter(Document.status == 'active')
            missing_validity = missing_q.count()
        except Exception as e:
            logger.error(f"Service health missing validity for {service} failed: {e}")
            missing_validity = 0

        sparkline = []
        for i in range(7):
            try:
                day = end_date - timedelta(days=6-i)
                day_total = Conversation.query.filter(
                    func.date(Conversation.timestamp) == day,
                    Conversation.service == service
                ).count()
                day_answered = Conversation.query.filter(
                    func.date(Conversation.timestamp) == day,
                    Conversation.service == service,
                    Conversation.source != 'fallback'
                ).count()
                day_coverage = round((day_answered / day_total * 100) if day_total else 100)
            except Exception as e:
                logger.error(f"Service health sparkline for {service} on {day} failed: {e}")
                day_coverage = 0
            sparkline.append(day_coverage)

        result.append({
            'name': service.capitalize(),
            'service': service,
            'coverage': coverage,
            'gaps': gaps,
            'critical_gaps': critical_gaps,
            'overrides': overrides,
            'expired': expired,
            'missing_validity': missing_validity,
            'sparkline': sparkline
        })
    return result


def get_reports_overview(start_date, end_date):
    try:
        submitted = Report.query.filter(
            func.date(Report.submitted_at) >= start_date,
            func.date(Report.submitted_at) <= end_date,
            Report.status == 'submitted'
        ).count()
        in_progress = Report.query.filter(
            func.date(Report.submitted_at) >= start_date,
            func.date(Report.submitted_at) <= end_date,
            Report.status == 'in_progress'
        ).count()
        resolved = Report.query.filter(
            func.date(Report.submitted_at) >= start_date,
            func.date(Report.submitted_at) <= end_date,
            Report.status == 'resolved'
        ).count()
        avg_time = db.session.query(
            func.avg(func.julianday(Report.resolved_at) -
                     func.julianday(Report.submitted_at))
        ).filter(
            func.date(Report.resolved_at) >= start_date,
            func.date(Report.resolved_at) <= end_date,
            Report.status == 'resolved'
        ).scalar() or 0
        status_counts = db.session.query(
            Report.status, func.count(Report.id)
        ).filter(
            func.date(Report.submitted_at) >= start_date,
            func.date(Report.submitted_at) <= end_date
        ).group_by(Report.status).all()
        distribution = [{'status': s, 'count': c} for s, c in status_counts]
    except Exception as e:
        logger.error(f"Reports overview failed: {e}")
        submitted = in_progress = resolved = 0
        avg_time = 0
        distribution = []

    return {
        'submitted': submitted,
        'in_progress': in_progress,
        'resolved': resolved,
        'avg_resolution_days': round(avg_time, 1),
        'distribution': distribution
    }


@bp.route('/api/export')
@login_required
def export_data():
    period = request.args.get('period', '30d')
    start_date, end_date = get_period_dates(period)
    data = get_analytics_data().json

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Metric', 'Value'])
    cw.writerow(['III', data['iii']])
    for k, v in data['iii_components'].items():
        cw.writerow([f'III Component - {k}', v])
    for k, v in data['risk_stability'].items():
        cw.writerow([f'Risk - {k}', v])
    # Add more as needed
    output = si.getvalue()
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=analytics_{period}.csv'}
    )


# Debug endpoints
@bp.route('/debug')
@login_required
def debug():
    period = request.args.get('period', '30d')
    start_date, end_date = get_period_dates(period)
    health = get_service_health(start_date, end_date)
    return jsonify(health)


@bp.route('/debug/iii')
@login_required
def debug_iii():
    period = request.args.get('period', '30d')
    start_date, end_date = get_period_dates(period)
    iii = calculate_iii_and_components(start_date, end_date)
    return jsonify(iii)


@bp.route('/debug/trends')
@login_required
def debug_trends():
    period = request.args.get('period', '30d')
    start_date, end_date = get_period_dates(period)
    trends = get_trends(start_date, end_date)
    return jsonify(trends)


# ===== Review Queue Endpoints (unchanged) =====
@bp.route('/api/review_queue')
@login_required
@manage_knowledge_required
def get_review_queue():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    query = ReviewQueue.query.order_by(ReviewQueue.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page)
    items = []
    for q in pagination.items:
        items.append({
            'id': q.id,
            'user_message': q.user_message,
            'intent': q.intent,
            'confidence': q.confidence,
            'generated_answer': q.generated_answer,
            'user_id': q.user_id,
            'created_at': q.created_at.isoformat(),
            'reviewed': q.reviewed,
        })
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })

@bp.route('/api/review_queue/<int:id>', methods=['PUT'])
@login_required
@manage_knowledge_required
def update_review_queue_item(id):
    item = ReviewQueue.query.get_or_404(id)
    data = request.get_json()
    action = data.get('action')
    if action not in ['accept', 'reject']:
        return jsonify({'error': 'Invalid action'}), 400
    item.reviewed = True
    item.reviewed_by = current_user.id
    item.reviewed_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})