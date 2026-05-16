from flask import Blueprint, render_template, request, jsonify, Response
from flask_login import login_required
from dashboard.extensions import db
from dashboard.models.conversation import Conversation
from datetime import datetime, timedelta
import csv
import logging
from sqlalchemy import func, desc
from io import StringIO

logger = logging.getLogger(__name__)

bp = Blueprint('conversations', __name__, url_prefix='/conversations')

def _json_extract(column, path):
    """Return a JSON extraction expression compatible with SQLite and PostgreSQL."""
    if db.engine.dialect.name == 'sqlite':
        # SQLite with JSON1 extension
        return db.func.json_extract(column, path)
    else:
        # PostgreSQL style
        return column[path].astext

def _apply_filters(query, args):
    """Apply common filters to the query (used for export and list)."""
    logger.info(f"Applying filters: {dict(args)}")

    # Date filter
    date_filter = args.get('date')
    if date_filter == 'today':
        query = query.filter(db.func.date(Conversation.timestamp) == datetime.utcnow().date())
    elif date_filter == 'last_7_days':
        week_ago = datetime.utcnow() - timedelta(days=7)
        query = query.filter(Conversation.timestamp >= week_ago)
    elif date_filter == 'last_30_days':
        month_ago = datetime.utcnow() - timedelta(days=30)
        query = query.filter(Conversation.timestamp >= month_ago)

    # User type filter – skip if 'all'
    user_type = args.get('user_type')
    if user_type and user_type != 'all':
        query = query.filter_by(user_type=user_type)

    # User ID filter – skip if 'all'
    user_id = args.get('user_id')
    if user_id and user_id != 'all':
        query = query.filter_by(user_id=user_id)

    # Department filter (via metadata_json) – skip if 'all'
    department = args.get('department')
    if department and department != 'all':
        dept_expr = _json_extract(Conversation.metadata_json, '$.department')
        query = query.filter(dept_expr == department)

    # Service filter – skip if 'all'
    service = args.get('service')
    if service and service != 'all':
        query = query.filter_by(service=service)

    # Search in user_message and bot_response
    search = args.get('search')
    if search:
        query = query.filter(
            db.or_(
                Conversation.user_message.ilike(f'%{search}%'),
                Conversation.bot_response.ilike(f'%{search}%')
            )
        )

    logger.info(f"Query count after filters: {query.count()}")
    return query

# ---------- Session list (new) ----------
@bp.route('/api/sessions')
@login_required
def list_sessions():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    # Base query grouping by session_id
    query = db.session.query(
        Conversation.session_id,
        func.min(Conversation.user_id).label('user_id'),
        func.min(Conversation.user_type).label('user_type'),
        func.max(Conversation.timestamp).label('last_activity'),
        func.count(Conversation.id).label('message_count'),
        func.min(Conversation.timestamp).label('first_activity')
    ).group_by(Conversation.session_id)

    # Apply filters
    user_id = request.args.get('user_id')
    if user_id and user_id != 'all':
        query = query.filter(Conversation.user_id == user_id)

    user_type = request.args.get('user_type')
    if user_type and user_type != 'all':
        query = query.filter(Conversation.user_type == user_type)

    service = request.args.get('service')
    if service and service != 'all':
        # Subquery to get session_ids with matching service
        subq = db.session.query(Conversation.session_id).filter(Conversation.service == service).distinct()
        query = query.filter(Conversation.session_id.in_(subq))

    date_filter = request.args.get('date')
    if date_filter == 'today':
        query = query.filter(func.date(Conversation.timestamp) == datetime.utcnow().date())
    elif date_filter == 'last_7_days':
        week_ago = datetime.utcnow() - timedelta(days=7)
        query = query.filter(Conversation.timestamp >= week_ago)
    elif date_filter == 'last_30_days':
        month_ago = datetime.utcnow() - timedelta(days=30)
        query = query.filter(Conversation.timestamp >= month_ago)

    search = request.args.get('search')
    if search:
        # Subquery to get session_ids where any message contains search term
        subq = db.session.query(Conversation.session_id).filter(
            db.or_(
                Conversation.user_message.ilike(f'%{search}%'),
                Conversation.bot_response.ilike(f'%{search}%')
            )
        ).distinct()
        query = query.filter(Conversation.session_id.in_(subq))

    # Order by last activity descending
    query = query.order_by(desc('last_activity'))

    # Pagination
    total = query.count()
    sessions = query.offset((page - 1) * per_page).limit(per_page).all()

    # For each session, get the last (most recent) user message preview
    items = []
    for sess in sessions:
        last_msg = Conversation.query.filter_by(session_id=sess.session_id)\
            .order_by(Conversation.timestamp.desc()).first()
        preview = last_msg.user_message[:50] + ('...' if len(last_msg.user_message) > 50 else '') if last_msg else ''
        items.append({
            'session_id': sess.session_id,
            'user_id': sess.user_id,
            'user_type': sess.user_type,
            'last_message': preview,  # renamed from first_message
            'message_count': sess.message_count,
            'last_activity': sess.last_activity.isoformat()
        })

    return jsonify({
        'items': items,
        'total': total,
        'page': page,
        'pages': (total + per_page - 1) // per_page
    })

# ---------- Full session thread ----------
@bp.route('/api/session/<session_id>')
@login_required
def get_session(session_id):
    messages = Conversation.query.filter_by(session_id=session_id)\
        .order_by(Conversation.timestamp.asc()).all()
    if not messages:
        return jsonify({'error': 'Session not found'}), 404

    thread = []
    for m in messages:
        thread.append({
            'id': m.id,
            'timestamp': m.timestamp.isoformat(),
            'user_message': m.user_message,
            'bot_response': m.bot_response,
            'intent': m.intent,
            'confidence': m.confidence,
            'source': m.source,
            'service': m.service,
            'metadata': m.metadata_json,
            'user_type': m.user_type,
            'user_id': m.user_id
        })
    return jsonify({
        'session_id': session_id,
        'thread': thread
    })

# ---------- Existing endpoints (keep for compatibility) ----------
@bp.route('/')
@login_required
def index():
    """Render conversations page with filter dropdown data."""
    # Get distinct user IDs
    user_ids = db.session.query(Conversation.user_id)\
        .filter(Conversation.user_id.isnot(None))\
        .distinct().order_by(Conversation.user_id).all()
    user_ids = [str(u[0]) for u in user_ids]

    # Get distinct departments from metadata_json
    dept_expr = _json_extract(Conversation.metadata_json, '$.department')
    dept_query = db.session.query(dept_expr)\
        .filter(dept_expr.isnot(None))\
        .distinct().all()
    departments = [d[0] for d in dept_query if d[0]]

    # Get distinct services
    services = db.session.query(Conversation.service)\
        .filter(Conversation.service.isnot(None))\
        .distinct().order_by(Conversation.service).all()
    services = [s[0] for s in services]

    return render_template('conversations.html',
                           user_ids=user_ids,
                           departments=departments,
                           services=services)

@bp.route('/api/list')
@login_required
def list_conversations():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    query = Conversation.query.order_by(Conversation.timestamp.desc())
    query = _apply_filters(query, request.args)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    items = []
    for c in pagination.items:
        items.append({
            'id': c.id,
            'timestamp': c.timestamp.isoformat(),
            'user_id': c.user_id,
            'user_type': c.user_type,
            'user_message': c.user_message[:50] + ('...' if len(c.user_message) > 50 else ''),
            'bot_response': c.bot_response[:50] + ('...' if c.bot_response and len(c.bot_response) > 50 else ''),
            'intent': c.intent,
            'source': c.source,
            'service': c.service,
            'department': c.get_metadata_field('department'),
        })
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })

@bp.route('/api/<int:id>')
@login_required
def get_conversation(id):
    conv = Conversation.query.get_or_404(id)
    return jsonify({
        'id': conv.id,
        'session_id': conv.session_id,
        'user_id': conv.user_id,
        'user_type': conv.user_type,
        'user_message': conv.user_message,
        'bot_response': conv.bot_response,
        'intent': conv.intent,
        'confidence': conv.confidence,
        'source': conv.source,
        'service': conv.service,
        'metadata': conv.metadata_json,
        'timestamp': conv.timestamp.isoformat()
    })

@bp.route('/api/user/<user_id>')
@login_required
def get_user_conversations(user_id):
    """Get all conversations for a specific user with aggregated data."""
    conversations = Conversation.query.filter_by(user_id=user_id)\
        .order_by(Conversation.timestamp.desc()).all()

    if not conversations:
        return jsonify({'error': 'User not found'}), 404

    total = len(conversations)
    first_seen = min(c.timestamp for c in conversations)
    last_seen = max(c.timestamp for c in conversations)

    dept_dist = {}
    for c in conversations:
        dept = c.get_metadata_field('department')
        if dept:
            dept_dist[dept] = dept_dist.get(dept, 0) + 1

    conv_list = []
    for c in conversations:
        conv_list.append({
            'id': c.id,
            'timestamp': c.timestamp.isoformat(),
            'user_message': c.user_message,
            'bot_response': c.bot_response,
            'intent': c.intent,
            'confidence': c.confidence,
            'service': c.service,
            'department': c.get_metadata_field('department'),
            'response_time_ms': c.get_metadata_field('response_time_ms'),
            'rag_used': c.get_metadata_field('rag_used'),
            'rasa_used': c.get_metadata_field('rasa_used'),
            'source': c.source,
            'user_type': c.user_type,
            'session_id': c.session_id,
        })

    return jsonify({
        'user': {
            'user_id': user_id,
            'first_seen': first_seen.isoformat(),
            'last_seen': last_seen.isoformat(),
            'total_conversations': total
        },
        'conversations': conv_list,
        'department_distribution': dept_dist,
        'total_conversations': total
    })

@bp.route('/api/export')
@login_required
def export_conversations():
    """Export filtered conversations as CSV."""
    query = Conversation.query.order_by(Conversation.timestamp.desc())
    query = _apply_filters(query, request.args)

    conversations = query.all()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Timestamp', 'User ID', 'User Type', 'User Message',
                 'Bot Response', 'Intent', 'Confidence', 'Source', 'Service',
                 'Department', 'Response Time (ms)', 'RAG Used', 'RASA Used'])
    for c in conversations:
        cw.writerow([
            c.id,
            c.timestamp.isoformat(),
            c.user_id,
            c.user_type,
            c.user_message,
            c.bot_response,
            c.intent,
            c.confidence,
            c.source,
            c.service,
            c.get_metadata_field('department', ''),
            c.get_metadata_field('response_time_ms', ''),
            c.get_metadata_field('rag_used', ''),
            c.get_metadata_field('rasa_used', '')
        ])

    output = si.getvalue()
    si.close()
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=conversations.csv'}
    )

@bp.route('/api/debug/count')
@login_required
def debug_count():
    total = Conversation.query.count()
    by_user_type = db.session.query(Conversation.user_type, db.func.count()).group_by(Conversation.user_type).all()
    return jsonify({'total': total, 'by_user_type': dict(by_user_type)})