from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from dashboard.extensions import db
from dashboard.models.conversation import Conversation
from dashboard.utils.llm_client import send_chat_message
import uuid
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('chat', __name__, url_prefix='/chat')


@bp.route('/')
@login_required
def index():
    """Render the chat interface with a session ID."""
    if 'chat_session_id' not in session:
        session['chat_session_id'] = str(uuid.uuid4())
    return render_template('chat.html', session_id=session.get('chat_session_id'))


@bp.route('/api/session')
@login_required
def get_session():
    """Return the current session ID."""
    return jsonify({'session_id': session.get('chat_session_id', '')})


@bp.route('/api/send', methods=['POST'])
@login_required
def send_message():
    """Send a message to the LLM Gateway and store the conversation."""
    data = request.get_json()
    message = data.get('message')
    if not message:
        return jsonify({'error': 'Message is required'}), 400

    session_id = session.get('chat_session_id', str(uuid.uuid4()))
    session['chat_session_id'] = session_id

    # Increase timeout to 180 seconds to accommodate slow hardware
    try:
        response_data = send_chat_message(
            message=message,
            user_id=current_user.id,
            session_id=session_id,
            source='dashboard',
            timeout=180   # seconds
        )
    except Exception as e:
        logger.error(f"Chat send error: {e}", exc_info=True)
        error_msg = str(e)
        if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
            return jsonify({'error': 'The request timed out. Please try again later.'}), 504
        return jsonify({'error': 'An internal error occurred. Please try again.'}), 500

    if response_data.get('error'):
        return jsonify({'error': response_data['error']}), 500

    # Save conversation to database
    conv = Conversation(
        session_id=session_id,
        user_id=current_user.id,
        user_type='admin',
        user_message=message,
        bot_response=response_data.get('response'),
        intent=response_data.get('intent'),
        confidence=response_data.get('confidence'),
        source=response_data.get('source'),
        service=response_data.get('service'),
        metadata_json=response_data.get('metadata')
    )
    db.session.add(conv)
    db.session.commit()

    return jsonify({
        'response': conv.bot_response,
        'intent': conv.intent,
        'confidence': conv.confidence,
        'source': conv.source,
        'service': conv.service,
        'metadata': conv.metadata_json,
        'timestamp': conv.timestamp.isoformat()
    })


@bp.route('/api/clear', methods=['POST'])
@login_required
def clear_session():
    """Clear the current chat session."""
    session.pop('chat_session_id', None)
    return jsonify({'status': 'cleared'})


@bp.route('/api/history')
@login_required
def get_history():
    """Return conversation history for the current session."""
    session_id = session.get('chat_session_id')
    if not session_id:
        return jsonify([])
    conversations = Conversation.query.filter_by(
        session_id=session_id,
        user_type='admin'
    ).order_by(Conversation.timestamp.asc()).limit(50).all()
    data = []
    for conv in conversations:
        data.append({
            'user_message': conv.user_message,
            'bot_response': conv.bot_response,
            'intent': conv.intent,
            'confidence': conv.confidence,
            'source': conv.source,
            'service': conv.service,
            'metadata': conv.metadata_json,
            'timestamp': conv.timestamp.isoformat()
        })
    return jsonify(data)