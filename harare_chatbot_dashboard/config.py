import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Flask
    SECRET_KEY = os.environ.get(
        'SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_APP = os.environ.get('FLASK_APP', 'app.py')
    FLASK_ENV = os.environ.get('FLASK_ENV', 'production')
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

    # Server
    HOST = os.environ.get('DASHBOARD_HOST', '127.0.0.1')
    PORT = int(os.environ.get('DASHBOARD_PORT', 5000))

    # Database
    PRODUCTION_DB_PATH = os.environ.get(
        'PRODUCTION_DB_PATH', 'data/production.db')
    if not os.path.isabs(PRODUCTION_DB_PATH):
        base_dir = os.path.abspath(os.path.dirname(__file__))
        PRODUCTION_DB_PATH = os.path.join(base_dir, PRODUCTION_DB_PATH)

    SQLALCHEMY_DATABASE_URI = f'sqlite:///{PRODUCTION_DB_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # External Services
    RAG_SYSTEM_URL = os.environ.get('RAG_SYSTEM_URL', 'http://localhost:8000')
    RAG_API_KEY = os.environ.get('RAG_API_KEY', '')
    LLM_GATEWAY_URL = os.environ.get(
        'LLM_GATEWAY_URL', 'http://localhost:8001')
    LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
    RASA_SYSTEM_URL = os.environ.get(
        'RASA_SYSTEM_URL', 'http://localhost:5005')
    RASA_API_KEY = os.environ.get('RASA_API_KEY', '')

    # Inbound API key
    INBOUND_API_KEY = os.environ.get(
        'INBOUND_API_KEY', 'change-this-in-production')

    # Redis (optional)
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

    # Duplicate detection window
    DUPLICATE_WINDOW_DAYS = int(os.environ.get('DUPLICATE_WINDOW_DAYS', 7))

    # PII redaction
    PII_REDACTION_DAYS = int(os.environ.get('PII_REDACTION_DAYS', 1))
    PII_ARCHIVE_RETENTION_YEARS = int(
        os.environ.get('PII_ARCHIVE_RETENTION_YEARS', 5))
    ENCRYPTION_KEY_FILE = os.environ.get(
        'ENCRYPTION_KEY_FILE', '.encryption_key')

    # Spam blacklist
    SPAM_BLACKLIST_FILE = os.environ.get(
        'SPAM_BLACKLIST_FILE', '/etc/spam_blacklist.txt')

    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/dashboard.log')

    # Pagination
    ITEMS_PER_PAGE = int(os.environ.get('ITEMS_PER_PAGE', 50))

    # RAG documents directory
    RAG_DOCUMENTS_PATH = os.environ.get(
        'RAG_DOCUMENTS_PATH', './shared_documents')

    # Service areas
    SERVICE_AREAS = os.environ.get(
        'SERVICE_AREAS', 'water,waste,health,transport,rates').split(',')

    # Content types
    CONTENT_TYPES = ['procedure', 'policy', 'fee_schedule',
                     'faq', 'emergency', 'contact_directory']

    # Caching
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'simple')
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT', 300))

    # Priority weights for knowledge gaps
    GAP_FREQUENCY_WEIGHT = 2
    GAP_RISK_WEIGHT = 10
    GAP_RECURRENCE_PENALTY = 15

    # Service risk levels (defaults)
    SERVICE_RISK_LEVELS = {
        'water': 'high',
        'waste': 'medium',
        'health': 'critical',
        'transport': 'medium',
        'rates': 'high',
        'electricity': 'high',
        'roads': 'medium',
        'parks': 'low',
        'planning': 'low',
        'emergency': 'critical'
    }

    # III weights
    III_COVERAGE_WEIGHT = 0.30
    III_KNOWLEDGE_HEALTH_WEIGHT = 0.25
    III_RECURRENCE_WEIGHT = 0.20
    III_RESOLUTION_QUALITY_WEIGHT = 0.15
    III_OVERRIDE_DEPENDENCE_WEIGHT = 0.10

    # Quick questions
    QUICK_QUESTIONS = [
        "Clinic hours?",
        "Pay water bill?",
        "Report pothole",
        "Burst pipe",
        "Waste collection schedule",
        "Council rates",
        "Birth certificate",
        "Business license",
        "Report illegal dumping",
        "Street light outage"
    ]

    # Rate limiting
    RATELIMIT_ENABLED = os.environ.get(
        'RATELIMIT_ENABLED', 'True').lower() == 'true'
    RATELIMIT_DEFAULT = os.environ.get(
        'RATELIMIT_DEFAULT', '200 per day;200 per hour')
    RATELIMIT_HEADERS_ENABLED = True
