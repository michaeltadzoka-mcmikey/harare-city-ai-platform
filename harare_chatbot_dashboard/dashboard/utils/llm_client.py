import requests
from flask import current_app
import logging

logger = logging.getLogger(__name__)

def get_llm_status():
    url = current_app.config['LLM_GATEWAY_URL'] + '/health'
    timeout = 10
    try:
        logger.debug(f"Calling LLM health at {url} with timeout {timeout}s")
        resp = requests.get(url, timeout=timeout)
        logger.debug(f"LLM health response: {resp.status_code} - {resp.text[:200]}")
        if resp.status_code == 200:
            data = resp.json()
            return {
                'status': data.get('status', 'unknown'),
                'sessions': data.get('active_sessions', 0),
                'avg_response': data.get('avg_response_time', 0)
            }
        else:
            logger.warning(f"LLM health returned {resp.status_code}")
            return {'status': 'offline', 'sessions': 0, 'avg_response': 0}
    except requests.exceptions.Timeout:
        logger.warning(f"LLM health check timeout after {timeout}s")
        return {'status': 'offline', 'sessions': 0, 'avg_response': 0}
    except requests.exceptions.ConnectionError:
        logger.warning("LLM health check connection refused")
        return {'status': 'offline', 'sessions': 0, 'avg_response': 0}
    except Exception as e:
        logger.error(f"LLM health check error: {e}")
        return {'status': 'offline', 'sessions': 0, 'avg_response': 0}

def send_chat_message(message, user_id, session_id, source='dashboard', timeout=180):
    """Send a chat message to the LLM Gateway. Returns structured response with documents in metadata.
    
    Args:
        timeout (int): Request timeout in seconds. Default 180 for slow hardware.
    """
    headers = {}
    if current_app.config['LLM_API_KEY']:
        headers['X-API-Key'] = current_app.config['LLM_API_KEY']
    payload = {
        'message': message,
        'user_id': str(user_id),
        'session_id': session_id,
        'source': source
    }
    url = current_app.config['LLM_GATEWAY_URL'] + '/chat'
    try:
        logger.debug(f"Sending chat message to {url} with timeout {timeout}s")
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            # Extract sources for document IDs
            sources = data.get('sources', [])
            documents = [src.get('id') for src in sources if src.get('id')] if sources else []
            # Build the final response with metadata.documents
            return {
                'response': data.get('response'),
                'intent': data.get('intent'),
                'confidence': data.get('metadata', {}).get('confidence', 0.0),
                'source': data.get('source', 'fallback'),
                'service': data.get('metadata', {}).get('service'),
                'metadata': {
                    'documents': documents,
                    'intent': data.get('intent'),
                    'confidence': data.get('metadata', {}).get('confidence'),
                    'source': data.get('source'),
                    'query_type': data.get('metadata', {}).get('query_type'),
                    'response_time': data.get('metadata', {}).get('response_time')
                }
            }
        else:
            logger.warning(f"Chat endpoint returned {resp.status_code}")
            return _offline_response("I'm sorry, the chat service is temporarily unavailable. Please try again later.")
    except requests.exceptions.Timeout:
        logger.warning(f"Chat request timeout after {timeout}s")
        return _offline_response("The request timed out. Please try again later.")
    except requests.exceptions.ConnectionError:
        logger.warning("Chat connection refused")
        return _offline_response("Unable to connect to the chat service. Please check your network.")
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return _offline_response("An unexpected error occurred.")

def _offline_response(msg):
    return {
        'response': msg,
        'intent': 'fallback',
        'confidence': 0,
        'source': 'offline',
        'service': None,
        'metadata': {}
    }