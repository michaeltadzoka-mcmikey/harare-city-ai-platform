from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from dashboard.extensions import db
from dashboard.models.escalation import Escalation
from dashboard.decorators import manage_knowledge_required
from datetime import datetime

bp = Blueprint('escalations', __name__, url_prefix='/escalations')

@bp.route('/')
@login_required
@manage_knowledge_required
def index():
    return render_template('escalations.html')

@bp.route('/api/list')
@login_required
@manage_knowledge_required
def list_escalations():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    query = Escalation.query
    if status and status != 'all':
        query = query.filter_by(status=status)
    pagination = query.order_by(Escalation.created_at.desc()).paginate(page=page, per_page=per_page)
    items = []
    for e in pagination.items:
        items.append({
            'id': e.id,
            'reference': e.reference,
            'query': e.query,
            'reason': e.reason,
            'status': e.status,
            'assigned_to': e.assigned_to,
            'created_at': e.created_at.isoformat()
        })
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })

@bp.route('/api/<int:id>', methods=['GET'])
@login_required
@manage_knowledge_required
def get_escalation(id):
    e = Escalation.query.get_or_404(id)
    return jsonify({
        'id': e.id,
        'reference': e.reference,
        'query': e.query,
        'session_id': e.session_id,
        'user_id': e.user_id,
        'reason': e.reason,
        'status': e.status,
        'assigned_to': e.assigned_to,
        'notes': e.notes,
        'created_at': e.created_at.isoformat(),
        'resolved_at': e.resolved_at.isoformat() if e.resolved_at else None
    })

@bp.route('/api/<int:id>/status', methods=['PUT'])
@login_required
@manage_knowledge_required
def update_escalation_status(id):
    e = Escalation.query.get_or_404(id)
    data = request.get_json()
    new_status = data.get('status')
    if new_status not in ['pending', 'in_progress', 'resolved']:
        return jsonify({'error': 'Invalid status'}), 400
    e.status = new_status
    if new_status == 'resolved':
        e.resolved_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/<int:id>/assign', methods=['PUT'])
@login_required
@manage_knowledge_required
def assign_escalation(id):
    e = Escalation.query.get_or_404(id)
    data = request.get_json()
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': 'User ID required'}), 400
    e.assigned_to = user_id
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/<int:id>/notes', methods=['POST'])
@login_required
@manage_knowledge_required
def add_escalation_note(id):
    e = Escalation.query.get_or_404(id)
    data = request.get_json()
    note = data.get('note')
    if not note:
        return jsonify({'error': 'Note required'}), 400
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    new_note = f"[{timestamp} {current_user.username}]: {note}\n"
    if e.notes:
        e.notes += new_note
    else:
        e.notes = new_note
    db.session.commit()
    return jsonify({'success': True})