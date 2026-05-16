from flask import Blueprint, request, jsonify, current_app
from dashboard.extensions import db
from dashboard.models.conversation import Conversation
from dashboard.models.knowledge_gap import KnowledgeGap
from dashboard.models.report import Report
from dashboard.models.feedback import CitizenFeedback
from datetime import datetime

bp = Blueprint('inbound', __name__)

def _check_auth():
    """Optional API key validation; if no key is configured, skip auth."""
    api_key = current_app.config.get('INBOUND_API_KEY')
    if not api_key:
        return True
    auth_header = request.headers.get('X-API-Key')
    return auth_header == api_key

@bp.route('/conversations', methods=['POST'])
def receive_conversation():
    if not _check_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    required = ['session_id', 'user_message', 'timestamp']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing {field}'}), 400

    conv = Conversation(
        session_id=data['session_id'],
        user_id=data.get('user_id'),
        user_type=data.get('user_type', 'citizen'),
        user_message=data['user_message'],
        bot_response=data.get('bot_response'),
        intent=data.get('intent'),
        confidence=data.get('confidence'),
        source=data.get('source'),
        service=data.get('service'),
        metadata_json=data.get('metadata'),
        timestamp=datetime.fromisoformat(data['timestamp']) if data.get('timestamp') else datetime.utcnow()
    )
    db.session.add(conv)
    db.session.commit()
    return jsonify({'status': 'ok'})

@bp.route('/knowledge_gaps', methods=['POST'])
def receive_knowledge_gap():
    if not _check_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    # Gateway sends 'question', not 'query'
    question = data.get('question') or data.get('query')
    if not question:
        return jsonify({'error': 'Missing question/query'}), 400

    # Duplicate detection (simple)
    similar = KnowledgeGap.query.filter(
        KnowledgeGap.question.ilike(f'%{question[:30]}%'),
        KnowledgeGap.status == 'open'
    ).first()
    if similar:
        similar.frequency += 1
        similar.last_asked = datetime.utcnow()
        db.session.commit()
        return jsonify({'gap_id': similar.id, 'updated': True})

    # Create new gap
    gap = KnowledgeGap(
        question=question,
        service=data.get('service'),
        service_risk=current_app.config['SERVICE_RISK_LEVELS'].get(data.get('service'), 'medium'),
        root_cause=data.get('root_cause', 'Other'),
        fallback_reason=data.get('gap_type'),
        confidence=data.get('confidence'),
        retrieval_result=data.get('retrieval_result'),
        frequency=1,
        status='open'
    )
    # Priority calculation (copied from your logic)
    frequency = gap.frequency
    service_risk = gap.service_risk
    risk_factor = 1 if service_risk == 'low' else 2 if service_risk == 'medium' else 3 if service_risk == 'high' else 5
    base_priority = (
        current_app.config['GAP_FREQUENCY_WEIGHT'] * frequency +
        current_app.config['GAP_RISK_WEIGHT'] * risk_factor
    )
    if base_priority >= 80:
        gap.impact = 'HIGH'
    elif base_priority >= 50:
        gap.impact = 'MEDIUM'
    else:
        gap.impact = 'LOW'
    gap.priority_score = base_priority

    db.session.add(gap)
    db.session.commit()
    return jsonify({'gap_id': gap.id, 'created': True})

@bp.route('/reports/status', methods=['GET'])
def get_report_status():
    if not _check_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    ref_id = request.args.get('ref')
    if not ref_id:
        return jsonify({'error': 'Missing ref'}), 400
    report = Report.query.filter_by(reference_id=ref_id).first()
    if not report:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({
        'status': report.status,
        'last_update': report.updated_at.isoformat() if report.updated_at else None
    })

@bp.route('/feedback', methods=['POST'])
def receive_feedback():
    if not _check_auth():
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    required = ['question', 'user_id', 'feedback_type']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing {field}'}), 400
    fb = CitizenFeedback(
        question=data['question'],
        user_id=data['user_id'],
        feedback_type=data['feedback_type'],
        details=data.get('details'),
        session_id=data.get('session_id'),
        timestamp=datetime.utcnow()
    )
    db.session.add(fb)
    db.session.commit()
    return jsonify({'status': 'feedback_received'})