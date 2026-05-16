import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from flask import Flask, request          # <-- Added 'request' import
from config import Config
from dashboard.extensions import db, login_manager, cache, limiter

# Import all models at module level
from dashboard.models import *  # noqa: F401


def create_app(config_class=Config):
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')
    app.config.from_object(config_class)

    # Set up basic logging for debugging
    logging.basicConfig(level=logging.DEBUG)

    # Ensure instance folders exist
    os.makedirs(os.path.dirname(app.config['LOG_FILE']), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, '..', 'data'), exist_ok=True)
    os.makedirs(app.config['RAG_DOCUMENTS_PATH'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    cache.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    limiter._exempt_when = lambda: request.remote_addr == "127.0.0.1"   # <-- ADDED: Exempt localhost from rate limits
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    # Global template context
    def get_now():
        return datetime.utcnow()
    app.context_processor(lambda: {'now': get_now})

    # Register blueprints with explicit names to avoid conflicts
    from dashboard.routes import auth, main, chat, conversations, documents, knowledge_gaps, analytics, reports, inbound, admin, users

    app.register_blueprint(auth.bp, name='auth')
    app.register_blueprint(main.bp, name='main')
    app.register_blueprint(chat.bp, name='chat')
    app.register_blueprint(conversations.bp, name='conversations')
    app.register_blueprint(documents.bp, name='documents')
    app.register_blueprint(knowledge_gaps.bp, name='knowledge_gaps')
    app.register_blueprint(analytics.bp, name='analytics')
    app.register_blueprint(reports.bp, name='reports')

    # --- Legacy blueprint for LLM Gateway routes (must be registered before inbound) ---
    from dashboard.routes import legacy
    app.register_blueprint(legacy.bp, name='legacy')

    # Inbound endpoints: prefix with /api to match gateway expectations
    app.register_blueprint(inbound.bp, url_prefix='/api', name='inbound')
    app.register_blueprint(admin.bp, name='admin')
    app.register_blueprint(users.users_bp, name='users')

    # --- New blueprints for intelligence upgrades ---
    from dashboard.routes import escalations
    app.register_blueprint(escalations.bp, name='escalations')
    # Memory inspector disabled for now – user memory is stored in Gateway
    # from dashboard.routes import memory
    # app.register_blueprint(memory.bp, name='memory')

    # Simple test route to verify app is working
    @app.route('/ping')
    def ping():
        return 'pong'

    # Setup file logging with daily rotation to avoid permission errors
    if not app.debug:
        file_handler = TimedRotatingFileHandler(
            app.config['LOG_FILE'], when='midnight', interval=1, backupCount=7)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Harare Dashboard startup')

    # User loader
    from dashboard.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Initialize scheduler (background jobs)
    if not app.debug or app.config.get('SCHEDULER_ENABLED_IN_DEBUG', False):
        from dashboard.scheduler import init_scheduler
        init_scheduler(app)

    # Shell context
    @app.shell_context_processor
    def make_shell_context():
        return {'db': db, 'User': User, 'cache': cache}

    return app