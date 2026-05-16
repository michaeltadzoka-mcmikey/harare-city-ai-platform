from flask import Blueprint, render_template, request, jsonify, make_response
import uuid
import logging
from dashboard.extensions import db
from dashboard.models.conversation import Conversation
from dashboard.utils.llm_client import send_chat_message

logger = logging.getLogger(__name__)

bp = Blueprint('public_chat', __name__, url_prefix='/public-chat')

def get_or_create_session_id():
    """Get existing session ID from cookie or create a new one."""
    session_id = request.cookies.get('public_chat_session')
    if not session_id:
        session_id = str(uuid.uuid4())
    return session_id

@bp.route('/')
def index():
    """Render the public chat interface (no login required)."""
    return render_template('public_chat_standalone.html')

@bp.route('/api/send', methods=['POST'])
def send_message():
    """Send a message to the LLM Gateway as a citizen (no auth)."""
    data = request.get_json()
    message = data.get('message')
    if not message:
        return jsonify({'error': 'Message is required'}), 400

    session_id = get_or_create_session_id()
    # Use session_id as the unique citizen identifier (not anonymous)
    user_id = session_id   # <-- unique ID per citizen session

    try:
        response_data = send_chat_message(
            message=message,
            user_id=user_id,
            session_id=session_id,
            source='public_web',
            timeout=180
        )
    except Exception as e:
        logger.error(f"Public chat send error: {e}", exc_info=True)
        return jsonify({'error': 'An internal error occurred. Please try again.'}), 500

    if response_data.get('error'):
        return jsonify({'error': response_data['error']}), 500

    # Save conversation with the unique user_id
    conv = Conversation(
        session_id=session_id,
        user_id=user_id,
        user_type='citizen',
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

    response = jsonify({
        'response': conv.bot_response,
        'intent': conv.intent,
        'confidence': conv.confidence,
        'source': conv.source,
        'service': conv.service,
        'metadata': conv.metadata_json,
        'timestamp': conv.timestamp.isoformat(),
        'id': conv.id
    })
    response.set_cookie('public_chat_session', session_id, max_age=86400*30, httponly=True, samesite='Lax')
    return response

@bp.route('/api/history')
def get_history():
    """Return conversation history for the current session."""
    session_id = get_or_create_session_id()
    conversations = Conversation.query.filter_by(
        session_id=session_id,
        user_type='citizen'
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
            'timestamp': conv.timestamp.isoformat(),
            'id': conv.id
        })
    return jsonify(data)

@bp.route('/api/clear', methods=['POST'])
def clear_session():
    """Clear the current public chat session (resets cookie)."""
    response = jsonify({'status': 'cleared'})
    response.set_cookie('public_chat_session', '', expires=0)
    return response

@bp.route('/api/feedback', methods=['POST'])
def feedback():
    """Store citizen feedback for a bot response (optional)."""
    data = request.get_json()
    conv_id = data.get('conversation_id')
    feedback_type = data.get('feedback')  # 'up' or 'down'
    # TODO: store in a feedback table or as metadata
    logger.info(f"Feedback for conversation {conv_id}: {feedback_type}")
    return jsonify({'status': 'ok'})