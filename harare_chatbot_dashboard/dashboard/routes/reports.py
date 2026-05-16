from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from dashboard.extensions import db
from dashboard.models.report import Report
from dashboard.models.audit_log import AuditLog
from dashboard.models.spam_keyword import SpamKeyword
from dashboard.decorators import manage_knowledge_required
from datetime import datetime, timedelta
from sqlalchemy import func, or_
import csv
from io import StringIO

bp = Blueprint('reports', __name__, url_prefix='/reports')

# ----------------------------------------------------------------------
# Helper: apply filters
# ----------------------------------------------------------------------
def apply_filters(query, args):
    """Apply common filters to a Report query."""
    status = args.get('status')
    urgency = args.get('urgency')
    duplicate = args.get('duplicate')
    spam = args.get('spam')
    date_range = args.get('date_range', '30d')
    search = args.get('search')

    if status and status != 'all':
        query = query.filter_by(status=status)
    if urgency and urgency != 'all':
        query = query.filter_by(urgency=urgency)
    if duplicate == 'true':
        query = query.filter_by(duplicate_flag=True)
    elif duplicate == 'false':
        query = query.filter_by(duplicate_flag=False)
    if spam == 'true':
        query = query.filter_by(spam_flag=True)
    elif spam == 'false':
        query = query.filter_by(spam_flag=False)
    if date_range:
        if date_range == 'today':
            query = query.filter(db.func.date(Report.submitted_at) == datetime.utcnow().date())
        elif date_range == '7d':
            week_ago = datetime.utcnow() - timedelta(days=7)
            query = query.filter(Report.submitted_at >= week_ago)
        elif date_range == '30d':
            month_ago = datetime.utcnow() - timedelta(days=30)
            query = query.filter(Report.submitted_at >= month_ago)
    if search:
        query = query.filter(
            or_(
                Report.reference_id.ilike(f'%{search}%'),
                Report.raw_text.ilike(f'%{search}%'),
                Report.standardized_location.ilike(f'%{search}%')
            )
        )
    return query

# ----------------------------------------------------------------------
# Admin routes
# ----------------------------------------------------------------------
@bp.route('/')
@login_required
def index():
    return render_template('reports.html')

@bp.route('/api/list')
@login_required
def list_reports():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    query = Report.query
    query = apply_filters(query, request.args)

    pagination = query.order_by(Report.submitted_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    items = []
    for r in pagination.items:
        items.append({
            'id': r.id,
            'reference_id': r.reference_id,
            'submitted_at': r.submitted_at.isoformat(),
            'standardized_type': r.standardized_type,
            'standardized_location': r.standardized_location,
            'urgency': r.urgency,
            'status': r.status,
            'duplicate_flag': r.duplicate_flag,
            'spam_flag': r.spam_flag,
            'raw_text_preview': r.raw_text[:50] + ('...' if len(r.raw_text) > 50 else '')
        })
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })

@bp.route('/api/report/<reference_id>')
@login_required
def get_report(reference_id):
    report = Report.query.filter_by(reference_id=reference_id).first_or_404()
    can_view_pii = current_user.can_manage_knowledge

    # Log PII access if original text is requested
    if can_view_pii and request.args.get('include_original') == 'true':
        log = AuditLog(
            user_id=current_user.id,
            username=current_user.username,
            action='view_original_pii',
            target_type='report',
            target_id=report.reference_id,
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()

    return jsonify({
        'id': report.id,
        'reference_id': report.reference_id,
        'raw_text': report.raw_text,
        'raw_text_original': report.raw_text_original if can_view_pii else None,
        'landmark': report.landmark,
        'standardized_type': report.standardized_type,
        'standardized_type_confidence': report.standardized_type_confidence,
        'standardized_location': report.standardized_location,
        'standardized_location_confidence': report.standardized_location_confidence,
        'urgency': report.urgency,
        'duplicate_flag': report.duplicate_flag,
        'duplicate_of': report.duplicate_of,
        'spam_flag': report.spam_flag,
        'spam_reason': report.spam_reason,
        'status': report.status,
        'assigned_department': report.assigned_department,
        'handled_by': report.handled_by,
        'handled_by_username': report.handled_by_user.username if report.handled_by_user else None,
        'internal_notes': report.internal_notes,
        'submitted_at': report.submitted_at.isoformat(),
        'last_updated': report.last_updated.isoformat() if report.last_updated else None,
        'resolved_at': report.resolved_at.isoformat() if report.resolved_at else None,
        'metadata_json': report.metadata_json
    })

@bp.route('/api/report/<reference_id>/audit')
@login_required
def get_report_audit(reference_id):
    """Return audit logs for a specific report."""
    logs = AuditLog.query.filter_by(target_type='report', target_id=reference_id)\
                         .order_by(AuditLog.timestamp.desc()).limit(50).all()
    return jsonify([{
        'timestamp': log.timestamp.isoformat(),
        'username': log.username,
        'action': log.action,
        'old_value': log.old_value,
        'new_value': log.new_value,
        'note': log.note
    } for log in logs])

@bp.route('/api/report/<reference_id>/status', methods=['PUT'])
@login_required
@manage_knowledge_required
def update_status(reference_id):
    report = Report.query.filter_by(reference_id=reference_id).first_or_404()
    data = request.get_json()
    new_status = data.get('status')
    if new_status not in ['submitted', 'in_progress', 'on_hold', 'resolved', 'closed']:
        return jsonify({'error': 'Invalid status'}), 400

    old_status = report.status
    report.status = new_status
    if new_status == 'resolved':
        report.resolved_at = datetime.utcnow()
    report.last_updated = datetime.utcnow()
    if data.get('handled_by'):
        report.handled_by = data['handled_by']
    db.session.commit()

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='update_report_status',
        target_type='report',
        target_id=report.reference_id,
        old_value=old_status,
        new_value=new_status,
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/report/<reference_id>/note', methods=['POST'])
@login_required
@manage_knowledge_required
def add_note(reference_id):
    report = Report.query.filter_by(reference_id=reference_id).first_or_404()
    data = request.get_json()
    note = data.get('note')
    if not note:
        return jsonify({'error': 'Note required'}), 400

    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    new_note = f"[{timestamp} {current_user.username}]: {note}"
    if report.internal_notes:
        report.internal_notes += "\n" + new_note
    else:
        report.internal_notes = new_note
    report.last_updated = datetime.utcnow()
    db.session.commit()

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='add_report_note',
        target_type='report',
        target_id=report.reference_id,
        new_value=note[:100],
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/report/<reference_id>/override', methods=['POST'])
@login_required
@manage_knowledge_required
def override_field(reference_id):
    report = Report.query.filter_by(reference_id=reference_id).first_or_404()
    data = request.get_json()
    field = data.get('field')
    value = data.get('value')
    justification = data.get('justification')
    if field not in ['standardized_type', 'standardized_location']:
        return jsonify({'error': 'Invalid field'}), 400
    if not justification or len(justification) < 10:
        return jsonify({'error': 'Justification too short'}), 400

    old_value = getattr(report, field)
    setattr(report, field, value)
    report.last_updated = datetime.utcnow()
    db.session.commit()

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='override_report_field',
        target_type='report',
        target_id=report.reference_id,
        old_value=old_value,
        new_value=value,
        note=justification,
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/report/<reference_id>/duplicate', methods=['POST'])
@login_required
@manage_knowledge_required
def mark_duplicate(reference_id):
    report = Report.query.filter_by(reference_id=reference_id).first_or_404()
    data = request.get_json()
    original_ref = data.get('original_reference')
    if not original_ref:
        return jsonify({'error': 'Original reference required'}), 400
    original = Report.query.filter_by(reference_id=original_ref).first()
    if not original:
        return jsonify({'error': 'Original report not found'}), 404
    report.duplicate_flag = True
    report.duplicate_of = original_ref
    db.session.commit()

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='mark_duplicate',
        target_type='report',
        target_id=report.reference_id,
        new_value=original_ref,
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/report/<reference_id>/spam', methods=['POST'])
@login_required
@manage_knowledge_required
def toggle_spam(reference_id):
    report = Report.query.filter_by(reference_id=reference_id).first_or_404()
    data = request.get_json()
    spam = data.get('spam', True)
    reason = data.get('reason')
    report.spam_flag = spam
    if spam:
        report.spam_reason = reason
    else:
        report.spam_reason = None
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/stats')
@login_required
def get_stats():
    total = Report.query.count()
    submitted = Report.query.filter_by(status='submitted').count()
    in_progress = Report.query.filter_by(status='in_progress').count()
    resolved = Report.query.filter_by(status='resolved').count()
    avg_time = db.session.query(
        func.avg(
            func.extract('epoch', Report.resolved_at - Report.submitted_at) / 86400.0
        )
    ).filter(Report.status == 'resolved').scalar() or 0
    return jsonify({
        'total': total,
        'submitted': submitted,
        'in_progress': in_progress,
        'resolved': resolved,
        'avg_resolution_days': round(avg_time, 1)
    })

@bp.route('/api/export')
@login_required
def export_reports():
    query = Report.query
    query = apply_filters(query, request.args)
    reports = query.order_by(Report.submitted_at.desc()).all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Reference ID', 'Submitted', 'Type', 'Location', 'Urgency', 'Status', 'Duplicate', 'Spam', 'Raw Text'])
    for r in reports:
        writer.writerow([
            r.reference_id,
            r.submitted_at.isoformat(),
            r.standardized_type or '',
            r.standardized_location or '',
            r.urgency,
            r.status,
            r.duplicate_flag,
            r.spam_flag,
            r.raw_text
        ])
    response = current_app.response_class(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=reports.csv'}
    )
    return response

# ----------------------------------------------------------------------
# Public API (for LLM Gateway)
# ----------------------------------------------------------------------
@bp.route('/api/inbound', methods=['POST'])
def inbound():
    auth_header = request.headers.get('X-API-Key')
    if auth_header != current_app.config['INBOUND_API_KEY']:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    required = ['raw_text']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing {field}'}), 400

    year = datetime.utcnow().year
    seq = Report.query.filter(Report.reference_id.like(f'HCC-RPT-{year}-%')).count() + 1
    ref_id = f"HCC-RPT-{year}-{seq:05d}"

    report = Report(
        reference_id=ref_id,
        raw_text=data['raw_text'],
        landmark=data.get('landmark'),
        standardized_type=data.get('standardized_type'),
        standardized_type_confidence=data.get('standardized_type_confidence'),
        standardized_location=data.get('standardized_location'),
        standardized_location_confidence=data.get('standardized_location_confidence'),
        urgency=data.get('urgency', 'medium'),
        duplicate_flag=data.get('duplicate_flag', False),
        duplicate_of=data.get('duplicate_of'),
        spam_flag=data.get('spam_flag', False),
        spam_reason=data.get('spam_reason'),
        metadata_json=data.get('metadata')
    )
    db.session.add(report)
    db.session.commit()

    audit = AuditLog(
        user_id=None,
        username='system',
        action='create_report',
        target_type='report',
        target_id=ref_id,
        ip_address=request.remote_addr
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({'reference_id': ref_id})

@bp.route('/api/status')
def public_status():
    # Rate limiting is applied via Flask‑Limiter (see app factory)
    ref = request.args.get('ref')
    if not ref:
        return jsonify({'error': 'Reference required'}), 400
    report = Report.query.filter_by(reference_id=ref).first()
    if not report:
        return jsonify({'error': 'Report not found'}), 404
    return jsonify({
        'reference_id': report.reference_id,
        'status': report.status,
        'last_updated': report.last_updated.isoformat() if report.last_updated else None,
        'resolved_at': report.resolved_at.isoformat() if report.resolved_at else None
    })

# ----------------------------------------------------------------------
# Aliases for LLM Gateway compatibility
# ----------------------------------------------------------------------
@bp.route('/api/reports', methods=['POST'])
def inbound_alias():
    """Alias for inbound endpoint (legacy)."""
    return inbound()

@bp.route('/api/reports/status')
def public_status_alias():
    """Alias for public status endpoint (legacy)."""
    return public_status()

# ----------------------------------------------------------------------
# Spam Blacklist Management
# ----------------------------------------------------------------------
@bp.route('/api/spam_keywords', methods=['GET'])
@login_required
@manage_knowledge_required
def get_spam_keywords():
    keywords = SpamKeyword.query.order_by(SpamKeyword.keyword).all()
    return jsonify([{'id': k.id, 'keyword': k.keyword} for k in keywords])

@bp.route('/api/spam_keywords', methods=['POST'])
@login_required
@manage_knowledge_required
def add_spam_keyword():
    data = request.get_json()
    keyword = data.get('keyword')
    if not keyword:
        return jsonify({'error': 'Keyword required'}), 400
    if SpamKeyword.query.filter_by(keyword=keyword).first():
        return jsonify({'error': 'Keyword already exists'}), 400
    k = SpamKeyword(keyword=keyword)
    db.session.add(k)
    db.session.commit()
    return jsonify({'id': k.id, 'keyword': k.keyword})

@bp.route('/api/spam_keywords/<int:id>', methods=['DELETE'])
@login_required
@manage_knowledge_required
def delete_spam_keyword(id):
    k = SpamKeyword.query.get_or_404(id)
    db.session.delete(k)
    db.session.commit()
    return jsonify({'success': True})