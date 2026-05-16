from flask import Blueprint, jsonify, request
from flask_login import login_required
from dashboard.extensions import db
from dashboard.utils.user_memory import user_memory
from dashboard.decorators import manage_knowledge_required
from datetime import datetime

bp = Blueprint('memory', __name__, url_prefix='/memory')

@bp.route('/api/<user_id>')
@login_required
@manage_knowledge_required
def get_memory(user_id):
    profile = user_memory.get_profile(user_id)
    return jsonify(profile)

@bp.route('/api/<user_id>', methods=['PUT'])
@login_required
@manage_knowledge_required
def update_memory(user_id):
    data = request.get_json()
    key = data.get('key')
    value = data.get('value')
    if not key or value is None:
        return jsonify({'error': 'Key and value required'}), 400
    profile = user_memory.get_profile(user_id)
    user_facts = profile.get('user_facts', {})
    if key in user_facts:
        # update in place
        if isinstance(user_facts[key], dict):
            user_facts[key]['value'] = value
            user_facts[key]['last_confirmed'] = datetime.utcnow().isoformat()
        else:
            user_facts[key] = value
        user_memory.merge_facts(user_id, {key: user_facts[key]})
    else:
        user_memory.merge_facts(user_id, {key: value})
    return jsonify({'success': True})