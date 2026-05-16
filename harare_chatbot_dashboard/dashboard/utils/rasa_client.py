import requests
from flask import current_app
import logging

logger = logging.getLogger(__name__)

def get_rasa_status():
    """Check RASA health."""
    try:
        url = current_app.config['RASA_SYSTEM_URL']
        resp = requests.get(url, timeout=1)
        if resp.status_code == 200:
            return {'status': 'healthy'}
        else:
            return {'status': 'degraded'}
    except requests.exceptions.Timeout:
        logger.warning("RASA health check timeout")
        return {'status': 'offline'}
    except requests.exceptions.ConnectionError:
        logger.warning("RASA health check connection refused")
        return {'status': 'offline'}
    except Exception as e:
        logger.error(f"RASA health check error: {e}")
        return {'status': 'offline'}