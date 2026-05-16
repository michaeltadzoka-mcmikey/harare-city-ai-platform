# dashboard/utils/data_sync.py
import requests
from flask import current_app
from dashboard.extensions import db
from dashboard.models.conversation import Conversation
from datetime import datetime

def sync_conversations_from_gateway():
    """Pull recent conversations from LLM Gateway."""
    url = f"{current_app.config['LLM_GATEWAY_URL']}/api/v1/conversations/recent"
    headers = {'X-API-Key': current_app.config['LLM_API_KEY']}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            count = 0
            for conv_data in data.get('conversations', []):
                existing = Conversation.query.filter_by(session_id=conv_data['session_id'], timestamp=conv_data['timestamp']).first()
                if not existing:
                    conv = Conversation(
                        session_id=conv_data['session_id'],
                        user_id=None,
                        user_type=conv_data.get('user_type', 'citizen'),
                        user_message=conv_data['user_message'],
                        bot_response=conv_data.get('bot_response'),
                        intent=conv_data.get('intent'),
                        confidence=conv_data.get('confidence'),
                        source=conv_data.get('source'),
                        service=conv_data.get('service'),
                        metadata_json=conv_data.get('metadata'),
                        timestamp=datetime.fromisoformat(conv_data['timestamp'])
                    )
                    db.session.add(conv)
                    count += 1
            db.session.commit()
            return count
    except Exception as e:
        current_app.logger.error(f"Sync failed: {e}")
        return 0
    return 0