from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def manage_users_required(f):
    """Decorator to require 'Manage Users' permission."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if not current_user.can_manage_users:
            flash('You do not have permission to manage users.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def manage_knowledge_required(f):
    """Decorator to require 'Manage Knowledge' permission."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if not current_user.can_manage_knowledge:
            flash('You do not have permission to modify knowledge.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

# Optional: a decorator for any authenticated user (though @login_ready from Flask-Login suffices)
def login_required(f):
    """Custom login required decorator (optional, but we can keep for consistency)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function