from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from dashboard.extensions import db
from dashboard.models.knowledge_gap import KnowledgeGap
from dashboard.models.draft import Draft
from dashboard.models.override import Override
from dashboard.models.audit_log import AuditLog
from dashboard.models.conversation import Conversation
from dashboard.decorators import manage_knowledge_required
from dashboard.utils.embedding import get_embedding, cosine_similarity
from dashboard.utils.rag_client import rag_validate_document
from datetime import datetime, timedelta
import json
import logging
import traceback
from sqlalchemy import func, cast, Date

logger = logging.getLogger(__name__)

bp = Blueprint('knowledge_gaps', __name__, url_prefix='/knowledge-gaps')

# ---------- Helper functions ----------
def recalc_priority(gap):
    """Recalculate priority_score and impact based on current data."""
    risk_factor = {
        'low': 1,
        'medium': 2,
        'high': 3,
        'critical': 5
    }.get(gap.service_risk, 1)
    base_priority = (
        current_app.config['GAP_FREQUENCY_WEIGHT'] * gap.frequency +
        current_app.config['GAP_RISK_WEIGHT'] * risk_factor +
        current_app.config['GAP_RECURRENCE_PENALTY'] * gap.recurrence_count
    )
    gap.base_priority = base_priority
    gap.priority_score = base_priority

    # Determine impact
    if base_priority >= 80:
        impact = 'HIGH'
    elif base_priority >= 50:
        impact = 'MEDIUM'
    else:
        impact = 'LOW'

    # Minimum impact floors
    if gap.service_risk == 'critical' and impact == 'LOW':
        impact = 'MEDIUM'
    if gap.recurrence_count > 0 and impact == 'LOW':
        impact = 'MEDIUM'

    gap.impact = impact
    return gap

def log_action(user_id, username, action, target_type, target_id, old_value=None, new_value=None, note=None):
    log = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        old_value=old_value,
        new_value=new_value,
        note=note,
        ip_address=request.remote_addr
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()

def infer_service_from_question(question: str) -> str:
    """Simple keyword‑based service inference for inbound gaps."""
    q = question.lower()
    if any(word in q for word in ['water', 'pipe', 'leak', 'sewer', 'drain']):
        return 'water'
    if any(word in q for word in ['rates', 'property', 'tax', 'valuation']):
        return 'rates'
    if any(word in q for word in ['waste', 'garbage', 'refuse', 'recycling']):
        return 'waste'
    if any(word in q for word in ['permit', 'license', 'application', 'zoning']):
        return 'permits'
    if any(word in q for word in ['health', 'clinic', 'hospital', 'vaccination']):
        return 'health'
    if any(word in q for word in ['road', 'pothole', 'street', 'traffic']):
        return 'roads'
    if any(word in q for word in ['park', 'recreation', 'playground']):
        return 'parks'
    if any(word in q for word in ['transport', 'bus', 'taxi', 'minibus']):
        return 'transport'
    return 'unknown'

def get_service_risk(service: str) -> str:
    """Get risk level for a service (from config or default)."""
    return current_app.config.get('SERVICE_RISK_LEVELS', {}).get(service, 'medium')

# ---------- Main page ----------
@bp.route('/')
@login_required
def index():
    services = current_app.config['SERVICE_AREAS']
    open_count = KnowledgeGap.query.filter_by(status='open').count()
    critical_count = KnowledgeGap.query.filter(
        KnowledgeGap.impact == 'HIGH',
        KnowledgeGap.priority_score >= 80
    ).count()
    recurring_count = KnowledgeGap.query.filter(KnowledgeGap.recurrence_count > 0).count()
    drafting_count = KnowledgeGap.query.filter_by(status='drafting').count()
    review_count = KnowledgeGap.query.filter_by(status='review').count()
    completed_count = KnowledgeGap.query.filter_by(status='completed').count()

    return render_template(
        'knowledge_gaps.html',
        services=services,
        open_count=open_count,
        critical_count=critical_count,
        recurring_count=recurring_count,
        drafting_count=drafting_count,
        review_count=review_count,
        completed_count=completed_count
    )

# ---------- API: List gaps ----------
@bp.route('/api/list')
@login_required
def list_gaps():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    priority = request.args.get('priority')
    service = request.args.get('service')
    status = request.args.get('status')
    search = request.args.get('search')

    query = KnowledgeGap.query
    if priority and priority != 'all':
        if priority == 'critical':
            query = query.filter(KnowledgeGap.impact == 'HIGH', KnowledgeGap.priority_score >= 80)
        elif priority == 'high':
            query = query.filter(KnowledgeGap.impact == 'HIGH', KnowledgeGap.priority_score < 80)
        elif priority == 'medium':
            query = query.filter_by(impact='MEDIUM')
        elif priority == 'low':
            query = query.filter_by(impact='LOW')
    if service and service != 'all':
        query = query.filter_by(service=service)
    if status and status != 'all':
        if status == 'recurring':
            query = query.filter(KnowledgeGap.recurrence_count > 0)
        else:
            query = query.filter_by(status=status)
    if search:
        query = query.filter(KnowledgeGap.question.ilike(f'%{search}%'))

    pagination = query.order_by(
        KnowledgeGap.priority_score.desc(),
        KnowledgeGap.last_asked.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    items = []
    for gap in pagination.items:
        items.append({
            'id': gap.id,
            'question': gap.question[:80] + ('...' if len(gap.question) > 80 else ''),
            'service': gap.service,
            'service_risk': gap.service_risk,
            'frequency': gap.frequency,
            'recurrence_count': gap.recurrence_count,
            'impact': gap.impact,
            'status': gap.status,
            'priority_score': gap.priority_score,
            'last_asked': gap.last_asked.isoformat() if gap.last_asked else None,
            'assigned_to': gap.assigned_to
        })
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })

# ---------- API: Single gap ----------
@bp.route('/api/gap/<int:gap_id>')
@login_required
def get_gap(gap_id):
    gap = KnowledgeGap.query.get_or_404(gap_id)
    assigned_name = gap.assigned_user.username if gap.assigned_user else None
    return jsonify({
        'id': gap.id,
        'question': gap.question,
        'service': gap.service,
        'service_risk': gap.service_risk,
        'root_cause': gap.root_cause,
        'fallback_reason': gap.fallback_reason,
        'confidence': gap.confidence,
        'retrieval_result': gap.retrieval_result,
        'first_asked': gap.first_asked.isoformat() if gap.first_asked else None,
        'last_asked': gap.last_asked.isoformat() if gap.last_asked else None,
        'frequency': gap.frequency,
        'recurrence_count': gap.recurrence_count,
        'base_priority': gap.base_priority,
        'priority_score': gap.priority_score,
        'impact': gap.impact,
        'status': gap.status,
        'assigned_to': gap.assigned_to,
        'assigned_to_name': assigned_name,
        'draft_id': gap.draft_id,
        'suggested_documents': gap.suggested_documents,
        'resolution_type': gap.resolution_type,
        'resolution_quality_score': gap.resolution_quality_score,
        'resolved_at': gap.resolved_at.isoformat() if gap.resolved_at else None,
        'resolved_by': gap.resolved_by,
        'notes': gap.notes,
        'embedding': gap.embedding
    })

# ---------- API: Create gap (manual admin) ----------
@bp.route('/api/gap', methods=['POST'])
@login_required
@manage_knowledge_required
def create_gap():
    data = request.get_json()
    required = ['question', 'service']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing field: {field}'}), 400

    embedding = get_embedding(data['question'])
    duplicate_of = None
    duplicate_window = current_app.config.get('DUPLICATE_WINDOW_DAYS', 7)
    since = datetime.utcnow() - timedelta(days=duplicate_window)

    if embedding:
        recent_gaps = KnowledgeGap.query.filter(
            KnowledgeGap.status.in_(['open', 'drafting', 'review']),
            KnowledgeGap.created_at >= since,
            KnowledgeGap.embedding.isnot(None)
        ).all()
        for gap in recent_gaps:
            if gap.embedding:
                similarity = cosine_similarity(embedding, gap.embedding)
                if similarity > 0.85:
                    duplicate_of = gap.id
                    gap.frequency += 1
                    gap.last_asked = datetime.utcnow()
                    recalc_priority(gap)
                    db.session.commit()
                    log_action(
                        user_id=current_user.id,
                        username=current_user.username,
                        action='auto_increment_duplicate',
                        target_type='knowledge_gap',
                        target_id=gap.id,
                        note=f"Duplicate detected from new question (sim={similarity:.2f})"
                    )
                    return jsonify({
                        'duplicate': True,
                        'existing_gap_id': gap.id,
                        'message': 'This question matches an existing knowledge gap. The existing gap frequency has been increased.'
                    }), 200

    frequency = data.get('frequency', 1)
    service_risk = data.get('service_risk', current_app.config['SERVICE_RISK_LEVELS'].get(data['service'], 'medium'))
    recurrence_count = data.get('recurrence_count', 0)

    gap = KnowledgeGap(
        question=data['question'],
        service=data['service'],
        service_risk=service_risk,
        root_cause=data.get('root_cause', 'Other'),
        fallback_reason=data.get('fallback_reason'),
        confidence=data.get('confidence'),
        retrieval_result=data.get('retrieval_result'),
        frequency=frequency,
        recurrence_count=recurrence_count,
        status='open',
        assigned_to=data.get('assigned_to'),
        suggested_documents=data.get('suggested_documents', []),
        embedding=embedding
    )
    recalc_priority(gap)
    db.session.add(gap)
    db.session.commit()

    log_action(
        user_id=current_user.id,
        username=current_user.username,
        action='create_gap',
        target_type='knowledge_gap',
        target_id=gap.id,
        new_value=json.dumps({'question': gap.question, 'service': gap.service})
    )
    return jsonify({'id': gap.id})

# ---------- NEW: Public inbound endpoint for LLM Gateway ----------
@bp.route('/api/inbound', methods=['POST'])
def inbound_gap():
    """
    Public endpoint for LLM Gateway to log knowledge gaps.
    Expects X-API-Key header matching INBOUND_API_KEY.
    Payload: {"query": "user question", "gap_type": "low_confidence|no_match", "confidence": 0.2, "suggested_action": "..."}
    """
    try:
        auth_header = request.headers.get('X-API-Key')
        expected_key = current_app.config.get('INBOUND_API_KEY')
        if not expected_key:
            logger.error("INBOUND_API_KEY not configured in dashboard")
            return jsonify({'error': 'Server configuration error'}), 500
        if auth_header != expected_key:
            logger.warning(f"Invalid API key: {auth_header}")
            return jsonify({'error': 'Unauthorized'}), 401

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON'}), 400

        question = data.get('query') or data.get('question')
        if not question:
            return jsonify({'error': 'Missing question'}), 400

        gap_type = data.get('gap_type', 'unknown')
        confidence = data.get('confidence', 0.0)
        suggested_action = data.get('suggested_action')

        service = infer_service_from_question(question)
        service_risk = get_service_risk(service)

        # Check for existing open gap (simple text match)
        existing = KnowledgeGap.query.filter(
            KnowledgeGap.status == 'open',
            KnowledgeGap.question.ilike(f'%{question[:50]}%')
        ).first()
        if existing:
            existing.frequency += 1
            existing.last_asked = datetime.utcnow()
            recalc_priority(existing)
            db.session.commit()
            logger.info(f"Incremented existing knowledge gap {existing.id} for question: {question[:50]}")
            return jsonify({'id': existing.id, 'updated': True})

        # Create new gap
        gap = KnowledgeGap(
            question=question,
            service=service,
            service_risk=service_risk,
            root_cause='Other',
            fallback_reason=gap_type,
            confidence=confidence,
            retrieval_result={'suggested_action': suggested_action} if suggested_action else None,
            frequency=1,
            recurrence_count=0,
            status='open',
            created_at=datetime.utcnow(),
            first_asked=datetime.utcnow(),
            last_asked=datetime.utcnow()
        )
        recalc_priority(gap)
        db.session.add(gap)
        db.session.commit()

        logger.info(f"Knowledge gap created from gateway: {gap.id} - {question[:50]}")
        return jsonify({'id': gap.id})

    except Exception as e:
        logger.error(f"Error in inbound_gap: {e}\n{traceback.format_exc()}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

# ---------- API: Update status ----------
@bp.route('/api/gap/<int:gap_id>/status', methods=['PUT'])
@login_required
@manage_knowledge_required
def update_gap_status(gap_id):
    gap = KnowledgeGap.query.get_or_404(gap_id)
    data = request.get_json()
    new_status = data.get('status')
    valid_statuses = ['open', 'drafting', 'review', 'completed']
    if new_status not in valid_statuses:
        return jsonify({'error': f'Invalid status. Must be one of {valid_statuses}'}), 400

    old_status = gap.status
    gap.status = new_status
    if new_status == 'completed':
        gap.resolved_at = datetime.utcnow()
        gap.resolved_by = current_user.id
        gap.resolution_type = data.get('resolution_type')
        if gap.resolution_type == 'document_created':
            gap.resolution_quality_score = 100
        elif gap.resolution_type == 'override_created':
            gap.resolution_quality_score = 70
        elif gap.resolution_type == 'duplicate':
            gap.resolution_quality_score = 50
        else:
            gap.resolution_quality_score = 30

    db.session.commit()
    log_action(
        user_id=current_user.id,
        username=current_user.username,
        action='update_gap_status',
        target_type='knowledge_gap',
        target_id=gap.id,
        old_value=old_status,
        new_value=new_status,
        note=data.get('notes')
    )
    return jsonify({'success': True})

# ---------- API: Assign gap ----------
@bp.route('/api/gap/<int:gap_id>/assign', methods=['POST'])
@login_required
@manage_knowledge_required
def assign_gap(gap_id):
    gap = KnowledgeGap.query.get_or_404(gap_id)
    data = request.get_json()
    user_id = data.get('user_id')
    gap.assigned_to = user_id
    db.session.commit()
    log_action(
        user_id=current_user.id,
        username=current_user.username,
        action='assign_gap',
        target_type='knowledge_gap',
        target_id=gap.id,
        note=f"Assigned to user {user_id}"
    )
    return jsonify({'success': True})

# ---------- API: Create draft from gap ----------
@bp.route('/api/gap/<int:gap_id>/draft', methods=['POST'])
@login_required
@manage_knowledge_required
def create_draft_from_gap(gap_id):
    gap = KnowledgeGap.query.get_or_404(gap_id)
    data = request.get_json()

    if gap.draft_id:
        return jsonify({'error': 'A draft already exists for this gap'}), 409

    similar_draft = Draft.query.filter(
        Draft.metadata_json['service'].astext == gap.service,
        Draft.metadata_json['title'].astext.ilike(f'%{gap.question[:30]}%'),
        Draft.status.in_(['draft', 'review'])
    ).first()
    if similar_draft:
        return jsonify({
            'conflict': True,
            'draft_id': similar_draft.id,
            'message': 'Another draft with similar content already exists.'
        }), 409

    draft = Draft(
        gap_id=gap.id,
        content=data.get('content', ''),
        metadata_json={
            'service': gap.service,
            'suggested_type': data.get('document_type', 'procedure'),
            'title': data.get('title', f"Answer: {gap.question[:50]}")
        },
        created_by=current_user.id,
        status='draft'
    )
    db.session.add(draft)
    db.session.commit()

    gap.draft_id = draft.id
    gap.status = 'drafting'
    db.session.commit()

    log_action(
        user_id=current_user.id,
        username=current_user.username,
        action='create_draft_from_gap',
        target_type='knowledge_gap',
        target_id=gap.id,
        note=f"Draft {draft.id} created"
    )
    return jsonify({'draft_id': draft.id})

# ---------- API: Create standalone draft (no gap) ----------
@bp.route('/api/draft', methods=['POST'])
@login_required
@manage_knowledge_required
def create_standalone_draft():
    data = request.get_json()
    required = ['service', 'content']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing {field}'}), 400

    draft = Draft(
        content=data['content'],
        metadata_json={
            'service': data['service'],
            'suggested_type': data.get('document_type', 'procedure'),
            'title': data.get('title', 'Untitled Draft')
        },
        created_by=current_user.id,
        status='draft'
    )
    db.session.add(draft)
    db.session.commit()
    return jsonify({'draft_id': draft.id})

# ---------- API: Get draft details ----------
@bp.route('/api/draft/<int:draft_id>')
@login_required
def get_draft(draft_id):
    draft = Draft.query.get_or_404(draft_id)
    return jsonify({
        'id': draft.id,
        'content': draft.content,
        'metadata': draft.metadata_json,
        'status': draft.status,
        'created_by': draft.created_by,
        'created_at': draft.created_at.isoformat() if draft.created_at else None
    })

# ---------- API: Submit draft for review (with RAG validation) ----------
@bp.route('/api/draft/<int:draft_id>/submit', methods=['POST'])
@login_required
@manage_knowledge_required
def submit_draft_for_review(draft_id):
    draft = Draft.query.get_or_404(draft_id)

    doc_data = {
        'document_id': f"DRAFT-{draft.id}",
        'title': draft.metadata_json.get('title', ''),
        'content': draft.content,
        'service_area': draft.metadata_json.get('service', ''),
        'content_type': draft.metadata_json.get('suggested_type', 'procedure'),
        'department': current_user.department,
        'owner_email': current_user.email,
        'valid_from': datetime.utcnow().date().isoformat(),
        'valid_to': None,
        'locations': ['Council-wide'],
        'topic_tags': [draft.metadata_json.get('service', '')],
        'authority_confidence': 0.9,
        'prerequisites': [],
        'related_documents': []
    }

    validation = rag_validate_document(doc_data)

    if not validation.get('valid', False):
        return jsonify({
            'success': False,
            'errors': validation.get('errors', [])
        }), 400

    draft.status = 'review'
    draft.submitted_by = current_user.id
    draft.submitted_at = datetime.utcnow()
    db.session.commit()

    log_action(
        user_id=current_user.id,
        username=current_user.username,
        action='submit_draft',
        target_type='draft',
        target_id=draft.id,
        note='Draft submitted for review'
    )
    return jsonify({'success': True})

# ---------- API: Resolve gap ----------
@bp.route('/api/gap/<int:gap_id>/resolve', methods=['POST'])
@login_required
@manage_knowledge_required
def resolve_gap(gap_id):
    gap = KnowledgeGap.query.get_or_404(gap_id)
    data = request.get_json()
    resolution_type = data.get('resolution_type')
    if resolution_type not in ['document_created', 'override_created', 'duplicate', 'invalid_question', 'no_action']:
        return jsonify({'error': 'Invalid resolution type'}), 400

    gap.status = 'completed'
    gap.resolved_at = datetime.utcnow()
    gap.resolved_by = current_user.id
    gap.resolution_type = resolution_type
    if resolution_type == 'document_created':
        gap.resolution_quality_score = 100
    elif resolution_type == 'override_created':
        gap.resolution_quality_score = 70
    elif resolution_type == 'duplicate':
        gap.resolution_quality_score = 50
    else:
        gap.resolution_quality_score = 30

    if data.get('document_id'):
        gap.suggested_documents = [data['document_id']]
    if data.get('override_id'):
        gap.notes = (gap.notes or '') + f"\nLinked override: {data['override_id']}"
    if data.get('notes'):
        gap.notes = (gap.notes or '') + f"\n{data['notes']}"

    db.session.commit()

    log_action(
        user_id=current_user.id,
        username=current_user.username,
        action='resolve_gap',
        target_type='knowledge_gap',
        target_id=gap.id,
        new_value=resolution_type,
        note=data.get('notes')
    )
    return jsonify({'success': True})

# ---------- API: Recurrence check (manual trigger) ----------
@bp.route('/api/recurrence-check', methods=['POST'])
@login_required
@manage_knowledge_required
def run_recurrence_check():
    threshold_days = 14
    since = datetime.utcnow() - timedelta(days=threshold_days)
    reopened = 0

    completed_gaps = KnowledgeGap.query.filter_by(status='completed').all()
    open_gaps = KnowledgeGap.query.filter_by(status='open').all()

    for gap in completed_gaps:
        similar = None
        if gap.embedding:
            for og in open_gaps:
                if og.embedding and og.id != gap.id:
                    sim = cosine_similarity(gap.embedding, og.embedding)
                    if sim > 0.85:
                        similar = og
                        break
        else:
            similar = KnowledgeGap.query.filter(
                KnowledgeGap.status == 'open',
                KnowledgeGap.service == gap.service,
                KnowledgeGap.first_asked >= since,
                KnowledgeGap.question.ilike(f'%{gap.question[:30]}%')
            ).first()

        if similar:
            gap.status = 'open'
            gap.recurrence_count += 1
            if gap.resolution_quality_score:
                gap.resolution_quality_score *= 0.7
            recalc_priority(gap)
            gap.frequency += similar.frequency
            similar.status = 'completed'
            similar.resolution_type = 'duplicate'
            similar.resolved_at = datetime.utcnow()
            similar.resolved_by = current_user.id
            similar.notes = (similar.notes or '') + f"\nMerged into gap {gap.id} due to recurrence"
            db.session.add(gap)
            db.session.add(similar)
            reopened += 1

            log_action(
                user_id=current_user.id,
                username=current_user.username,
                action='recurrence_reopen',
                target_type='knowledge_gap',
                target_id=gap.id,
                note=f"Reopened due to similar gap {similar.id}"
            )

    db.session.commit()
    return jsonify({'reopened': reopened})

# ---------- API: Merge gaps ----------
@bp.route('/api/merge', methods=['POST'])
@login_required
@manage_knowledge_required
def merge_gaps():
    data = request.get_json()
    keep_id = data.get('keep_id')
    merge_id = data.get('merge_id')
    if not keep_id or not merge_id:
        return jsonify({'error': 'Both gap IDs required'}), 400
    keep = KnowledgeGap.query.get(keep_id)
    merge = KnowledgeGap.query.get(merge_id)
    if not keep or not merge:
        return jsonify({'error': 'One or both gaps not found'}), 404

    keep.frequency += merge.frequency
    keep.recurrence_count += merge.recurrence_count
    keep.notes = (keep.notes or '') + f"\nMerged from gap {merge.id}: {merge.question[:50]}..."
    recalc_priority(keep)

    merge.status = 'completed'
    merge.resolution_type = 'duplicate'
    merge.resolved_at = datetime.utcnow()
    merge.resolved_by = current_user.id
    merge.notes = (merge.notes or '') + f"\nMerged into gap {keep.id}"

    db.session.commit()

    log_action(
        user_id=current_user.id,
        username=current_user.username,
        action='merge_gaps',
        target_type='knowledge_gap',
        target_id=f"{keep_id},{merge_id}",
        note=f"Merged gap {merge_id} into {keep_id}"
    )
    return jsonify({'success': True})

# ---------- API: Stats (top bar and health) ----------
@bp.route('/api/stats')
@login_required
def get_stats():
    try:
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        total_queries = Conversation.query.filter(
            Conversation.timestamp >= thirty_days_ago
        ).count()
    except Exception:
        total_queries = 0

    open_gaps = KnowledgeGap.query.filter_by(status='open').all()
    weighted_sum = sum(g.priority_score for g in open_gaps)
    max_possible = 100
    if total_queries > 0:
        health = max(0, 100 - (weighted_sum / max_possible / total_queries * 100))
    else:
        health = max(0, 100 - (weighted_sum / (max_possible * len(open_gaps) if open_gaps else 1) * 100))

    week_ago = datetime.utcnow() - timedelta(days=7)
    new_last_week = KnowledgeGap.query.filter(KnowledgeGap.created_at >= week_ago).count()
    resolved_last_week = KnowledgeGap.query.filter(
        KnowledgeGap.resolved_at >= week_ago
    ).count()
    trend = "Worsening" if new_last_week > resolved_last_week else "Improving"

    return jsonify({
        'open': KnowledgeGap.query.filter_by(status='open').count(),
        'critical': KnowledgeGap.query.filter(
            KnowledgeGap.impact == 'HIGH',
            KnowledgeGap.priority_score >= 80
        ).count(),
        'recurring': KnowledgeGap.query.filter(KnowledgeGap.recurrence_count > 0).count(),
        'trend': trend,
        'health': round(health, 1),
        'new_last_week': new_last_week,
        'resolved_last_week': resolved_last_week
    })

# ---------- API: Metrics (service breakdown, priority distribution) ----------
@bp.route('/api/metrics')
@login_required
def get_metrics():
    services = db.session.query(
        KnowledgeGap.service,
        func.count(KnowledgeGap.id).label('count'),
        func.avg(KnowledgeGap.priority_score).label('avg_priority')
    ).filter_by(status='open').group_by(KnowledgeGap.service).all()

    service_stats = [{'service': s, 'count': c, 'avg_priority': round(a, 1) if a else 0}
                     for s, c, a in services]

    priority_counts = {
        'critical': KnowledgeGap.query.filter(
            KnowledgeGap.impact == 'HIGH',
            KnowledgeGap.priority_score >= 80
        ).count(),
        'high': KnowledgeGap.query.filter(
            KnowledgeGap.impact == 'HIGH',
            KnowledgeGap.priority_score < 80
        ).count(),
        'medium': KnowledgeGap.query.filter_by(impact='MEDIUM').count(),
        'low': KnowledgeGap.query.filter_by(impact='LOW').count()
    }

    avg_resolution = db.session.query(
        func.avg(func.julianday(KnowledgeGap.resolved_at) - func.julianday(KnowledgeGap.created_at))
    ).filter(KnowledgeGap.resolved_at.isnot(None)).scalar() or 0

    return jsonify({
        'service_stats': service_stats,
        'priority_counts': priority_counts,
        'avg_resolution_days': round(avg_resolution, 1)
    })

# ---------- API: Trends (daily counts) ----------
@bp.route('/api/trends')
@login_required
def get_trends():
    days = request.args.get('days', 30, type=int)
    end = datetime.utcnow().date()
    start = end - timedelta(days=days)

    try:
        created = db.session.query(
            func.date(KnowledgeGap.created_at).label('date'),
            func.count(KnowledgeGap.id).label('count')
        ).filter(KnowledgeGap.created_at >= start).group_by('date').all()

        resolved = db.session.query(
            func.date(KnowledgeGap.resolved_at).label('date'),
            func.count(KnowledgeGap.id).label('count')
        ).filter(KnowledgeGap.resolved_at >= start).group_by('date').all()

        return jsonify({
            'created': [{'date': str(d), 'count': c} for d, c in created],
            'resolved': [{'date': str(d), 'count': c} for d, c in resolved]
        })
    except Exception as e:
        logger.error(f"Trends query failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# ---------- API: Similar gaps ----------
@bp.route('/api/gap/<int:gap_id>/similar')
@login_required
def get_similar_gaps(gap_id):
    gap = KnowledgeGap.query.get_or_404(gap_id)
    if not gap.embedding:
        return jsonify([])
    threshold = 0.7
    similar = []
    all_gaps = KnowledgeGap.query.filter(KnowledgeGap.id != gap_id).all()
    for other in all_gaps:
        if other.embedding:
            sim = cosine_similarity(gap.embedding, other.embedding)
            if sim > threshold:
                similar.append({
                    'id': other.id,
                    'question': other.question,
                    'similarity': round(sim, 2),
                    'frequency': other.frequency,
                    'status': other.status
                })
    return jsonify(sorted(similar, key=lambda x: -x['similarity'])[:20])

# ---------- API: Recurrence list ----------
@bp.route('/api/recurrence/list')
@login_required
def get_recurrence_list():
    recurring = KnowledgeGap.query.filter(KnowledgeGap.recurrence_count > 0).all()
    items = []
    for gap in recurring:
        items.append({
            'id': gap.id,
            'question': gap.question[:80],
            'service': gap.service,
            'recurrence_count': gap.recurrence_count,
            'last_resolved': gap.resolved_at.isoformat() if gap.resolved_at else None,
            'current_frequency': gap.frequency
        })
    return jsonify(items)

# ---------- API: Audit log ----------
@bp.route('/api/audit')
@login_required
def get_audit():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    target_id = request.args.get('target_id')

    query = AuditLog.query.order_by(AuditLog.timestamp.desc())
    if target_id:
        query = query.filter_by(target_id=target_id)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    items = []
    for log in pagination.items:
        items.append({
            'timestamp': log.timestamp.isoformat(),
            'user': log.username,
            'action': log.action,
            'target_type': log.target_type,
            'target_id': log.target_id,
            'old_value': log.old_value,
            'new_value': log.new_value,
            'note': log.note,
            'ip': log.ip_address
        })
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })

# ---------- API: Draft conflict check ----------
@bp.route('/api/draft/conflict', methods=['POST'])
@login_required
@manage_knowledge_required
def check_draft_conflict():
    data = request.get_json()
    service = data.get('service')
    question = data.get('question')
    if not service or not question:
        return jsonify({'error': 'Missing service or question'}), 400

    similar = Draft.query.filter(
        Draft.metadata_json['service'].astext == service,
        Draft.metadata_json['title'].astext.ilike(f'%{question[:30]}%'),
        Draft.status.in_(['draft', 'review'])
    ).first()
    if similar:
        return jsonify({
            'conflict': True,
            'draft_id': similar.id,
            'message': 'A similar draft already exists.'
        })
    return jsonify({'conflict': False})