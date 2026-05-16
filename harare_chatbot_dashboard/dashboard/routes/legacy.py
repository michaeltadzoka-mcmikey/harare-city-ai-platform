from flask import Blueprint, request, jsonify
from dashboard.extensions import db
from dashboard.models.report import Report

bp = Blueprint('legacy', __name__, url_prefix='')


@bp.route('/api/reports/status')
def api_reports_status():
    """Public status endpoint for the LLM Gateway."""
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


@bp.route('/api/reports', methods=['POST'])
def api_reports_create():
    """Alias for inbound report creation (from LLM Gateway)."""
    # Forward to the existing inbound endpoint
    from dashboard.routes.reports import inbound
    return inbound()