# dashboard/routes/conflicts.py
# New routes for v3.2: Conflict Queue and Provisional Resolutions management

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from dashboard.extensions import db
from dashboard.models.conflict import Conflict, ProvisionalResolution
from dashboard.models.document import Document
from dashboard.models.audit_log import AuditLog
from dashboard.decorators import manage_knowledge_required
from datetime import datetime, timedelta

bp = Blueprint('conflicts', __name__, url_prefix='/documents/api/conflicts')

# ------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------
def _log_conflict_action(conflict, action, note=None):
    """Helper to log conflict-related actions."""
    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action=action,
        target_type='conflict',
        target_id=str(conflict.id),
        note=note or f"Conflict {conflict.id}: {action}"
    )
    db.session.add(log)
    db.session.commit()

# ------------------------------------------------------------
# Conflict Queue endpoints
# ------------------------------------------------------------
@bp.route('/')
@login_required
def list_conflicts():
    """List unresolved conflicts."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', 'unresolved')  # unresolved, all

    query = Conflict.query
    if status == 'unresolved':
        query = query.filter_by(status='unresolved')
    elif status == 'provisional':
        query = query.filter_by(status='provisionally_resolved')
    elif status == 'resolved':
        query = query.filter_by(status='resolved')

    pagination = query.order_by(Conflict.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    items = []
    for c in pagination.items:
        items.append({
            'id': c.id,
            'doc1': {
                'id': c.doc1.id,
                'document_id': c.doc1.document_id,
                'title': c.doc1.title,
                'service': c.doc1.service_area
            },
            'doc2': {
                'id': c.doc2.id,
                'document_id': c.doc2.document_id,
                'title': c.doc2.title,
                'service': c.doc2.service_area
            },
            'reason': c.reason,
            'status': c.status,
            'created_at': c.created_at.isoformat() if c.created_at else None,
            'last_notified': c.last_notified.isoformat() if c.last_notified else None,
            'provisional': c.provisional.to_dict() if c.provisional else None
        })

    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })

@bp.route('/<int:conflict_id>')
@login_required
def get_conflict(conflict_id):
    """Get details of a specific conflict."""
    conflict = Conflict.query.get_or_404(conflict_id)
    return jsonify({
        'id': conflict.id,
        'doc1': {
            'id': conflict.doc1.id,
            'document_id': conflict.doc1.document_id,
            'title': conflict.doc1.title,
            'service': conflict.doc1.service_area,
            'content_type': conflict.doc1.content_type,
            'valid_from': conflict.doc1.valid_from.isoformat() if conflict.doc1.valid_from else None,
            'valid_to': conflict.doc1.valid_to.isoformat() if conflict.doc1.valid_to else None
        },
        'doc2': {
            'id': conflict.doc2.id,
            'document_id': conflict.doc2.document_id,
            'title': conflict.doc2.title,
            'service': conflict.doc2.service_area,
            'content_type': conflict.doc2.content_type,
            'valid_from': conflict.doc2.valid_from.isoformat() if conflict.doc2.valid_from else None,
            'valid_to': conflict.doc2.valid_to.isoformat() if conflict.doc2.valid_to else None
        },
        'reason': conflict.reason,
        'status': conflict.status,
        'created_at': conflict.created_at.isoformat() if conflict.created_at else None,
        'provisional': {
            'id': conflict.provisional.id,
            'selected_doc_id': conflict.provisional.selected_doc_id,
            'selected_doc_title': conflict.provisional.selected_doc.title,
            'justification': conflict.provisional.justification,
            'resolved_at': conflict.provisional.resolved_at.isoformat(),
            'review_status': conflict.provisional.review_status
        } if conflict.provisional else None
    })

@bp.route('/<int:conflict_id>/resolve', methods=['POST'])
@login_required
@manage_knowledge_required
def resolve_conflict(conflict_id):
    """
    Manually resolve a conflict.
    Expected JSON: { "resolution": "retire_one", "selected_doc_id": 123, "justification": "..." }
    """
    conflict = Conflict.query.get_or_404(conflict_id)
    data = request.get_json()
    resolution = data.get('resolution')
    justification = data.get('justification', '')
    selected_doc_id = data.get('selected_doc_id')

    if not resolution:
        return jsonify({'error': 'Resolution method required'}), 400

    # Update conflict record
    conflict.status = 'resolved'
    conflict.resolved_at = datetime.utcnow()
    conflict.resolved_by = current_user.id
    conflict.resolution_notes = justification

    # If there was a provisional resolution, mark it as reviewed/overridden
    if conflict.provisional:
        prov = conflict.provisional
        prov.review_status = 'overridden' if resolution != 'confirm_provisional' else 'confirmed'
        prov.reviewed_by = current_user.id
        prov.reviewed_at = datetime.utcnow()
        prov.review_notes = justification

    # Perform the actual document changes based on resolution type
    if resolution == 'retire_one':
        if not selected_doc_id:
            return jsonify({'error': 'selected_doc_id required for retire_one'}), 400
        # Retire the other document (set valid_to to yesterday)
        other_doc_id = conflict.doc1_id if conflict.doc2_id == selected_doc_id else conflict.doc2_id
        other_doc = Document.query.get(other_doc_id)
        if other_doc:
            other_doc.valid_to = datetime.utcnow().date() - timedelta(days=1)
            other_doc.status = 'archived'
    elif resolution == 'override':
        # Create an override via the overrides API? Or just mark as resolved?
        # For now, we just log that an override will be created separately.
        pass
    elif resolution == 'confirm_provisional':
        # Already resolved; just confirm
        pass
    else:
        return jsonify({'error': f'Unknown resolution method: {resolution}'}), 400

    db.session.commit()
    _log_conflict_action(conflict, 'resolve', f'Resolved via {resolution}: {justification}')
    return jsonify({'success': True})

# ------------------------------------------------------------
# Provisional Resolutions Queue
# ------------------------------------------------------------
@bp.route('/provisional')
@login_required
def list_provisional():
    """List provisional resolutions pending review."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', 'pending')  # pending, confirmed, overridden, all

    query = ProvisionalResolution.query.join(Conflict)
    if status != 'all':
        query = query.filter(ProvisionalResolution.review_status == status)

    pagination = query.order_by(ProvisionalResolution.resolved_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    items = []
    for p in pagination.items:
        items.append({
            'id': p.id,
            'conflict_id': p.conflict_id,
            'selected_doc': {
                'id': p.selected_doc.id,
                'document_id': p.selected_doc.document_id,
                'title': p.selected_doc.title
            },
            'justification': p.justification,
            'resolved_at': p.resolved_at.isoformat(),
            'review_status': p.review_status,
            'review_deadline': (p.resolved_at + timedelta(days=7)).isoformat(),
            'conflict': {
                'id': p.conflict.id,
                'doc1_title': p.conflict.doc1.title,
                'doc2_title': p.conflict.doc2.title
            }
        })

    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })

@bp.route('/provisional/<int:prov_id>/review', methods=['POST'])
@login_required
@manage_knowledge_required
def review_provisional(prov_id):
    """
    Review a provisional resolution.
    Expected JSON: { "action": "confirm", "notes": "..." }
    """
    prov = ProvisionalResolution.query.get_or_404(prov_id)
    data = request.get_json()
    action = data.get('action')
    notes = data.get('notes', '')

    if not action:
        return jsonify({'error': 'Action required'}), 400

    prov.reviewed_by = current_user.id
    prov.reviewed_at = datetime.utcnow()
    prov.review_notes = notes

    if action == 'confirm':
        prov.review_status = 'confirmed'
        # Mark conflict as resolved if not already
        if prov.conflict.status != 'resolved':
            prov.conflict.status = 'resolved'
            prov.conflict.resolved_at = datetime.utcnow()
            prov.conflict.resolved_by = current_user.id
            prov.conflict.resolution_notes = f"Provisional confirmed: {notes}"
    elif action == 'override':
        prov.review_status = 'overridden'
        # Conflict remains unresolved (or can be reopened)
        prov.conflict.status = 'unresolved'
        # Optionally, log that override will be created
    elif action == 'reopen':
        prov.review_status = 'reopened'
        prov.conflict.status = 'unresolved'
    else:
        return jsonify({'error': f'Unknown action: {action}'}), 400

    db.session.commit()
    _log_conflict_action(prov.conflict, 'review_provisional', f'{action}: {notes}')
    return jsonify({'success': True})

# ------------------------------------------------------------
# Background job (to be called by scheduler)
# ------------------------------------------------------------
def check_unresolved_conflicts():
    """Check for conflicts that have been unresolved for >48h, >5d, >14d."""
    now = datetime.utcnow()
    # 48h
    two_days_ago = now - timedelta(hours=48)
    old_conflicts = Conflict.query.filter(
        Conflict.status == 'unresolved',
        Conflict.created_at <= two_days_ago
    ).all()
    for c in old_conflicts:
        # Notify Manage Knowledge users
        current_app.logger.info(f"Conflict {c.id} unresolved for >48h")
        # TODO: send notification

    # 5 days
    five_days_ago = now - timedelta(days=5)
    very_old = Conflict.query.filter(
        Conflict.status == 'unresolved',
        Conflict.created_at <= five_days_ago
    ).all()
    for c in very_old:
        # Notify both-flags users
        current_app.logger.info(f"Conflict {c.id} unresolved for >5d")

    # 14 days -> auto-resolve provisionally
    fourteen_days_ago = now - timedelta(days=14)
    to_auto = Conflict.query.filter(
        Conflict.status == 'unresolved',
        Conflict.created_at <= fourteen_days_ago
    ).all()
    for c in to_auto:
        # Auto-resolve using highest precedence document
        # This logic should mirror the precedence engine
        # For simplicity, we'll pick the doc with higher priority according to our rules
        # (In reality, you'd call the precedence engine)
        # For now, just pick the first one.
        selected_doc_id = c.doc1_id  # placeholder
        prov = ProvisionalResolution(
            conflict_id=c.id,
            selected_doc_id=selected_doc_id,
            justification="Auto-resolved after 14 days"
        )
        c.status = 'provisionally_resolved'
        c.provisional_at = now
        db.session.add(prov)
        db.session.commit()
        current_app.logger.info(f"Conflict {c.id} auto-resolved provisionally")