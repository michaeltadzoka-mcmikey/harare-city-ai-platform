"""
User management routes (Users & Roles module)
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from dashboard.extensions import db
from dashboard.models.user import User
from dashboard.models.audit_log import AuditLog
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)

users_bp = Blueprint('users', __name__, url_prefix='/users')


def admin_required(f):
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.can_manage_users:
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function


def log_action(action, target_user_id=None, old_value=None, new_value=None, note=None):
    """Create an audit log entry using the current db session."""
    try:
        permission_snapshot = {
            'can_manage_users': current_user.can_manage_users,
            'can_manage_knowledge': current_user.can_manage_knowledge
        }
        full_note = note if note else ""
        full_note += f" | Permission snapshot: {json.dumps(permission_snapshot)}"

        log = AuditLog(
            user_id=current_user.id,
            username=current_user.username,
            action=action,
            target_type='user' if target_user_id else None,
            target_id=str(target_user_id) if target_user_id else None,
            old_value=old_value,
            new_value=new_value,
            note=full_note.strip(),
            ip_address=request.remote_addr
        )
        log.set_hash_chain()
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")
        db.session.rollback()


@users_bp.route('/')
@login_required
@admin_required
def index():
    return render_template('admin/users.html')


@users_bp.route('/api/list')
@login_required
@admin_required
def list_users():
    try:
        users = User.query.order_by(User.email).all()
        return jsonify({
            'users': [u.to_dict() for u in users],
            'total': len(users)
        })
    except Exception as e:
        logger.error(f"Error in list_users: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@users_bp.route('/api/user/<int:user_id>')
@login_required
@admin_required
def get_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict())


@users_bp.route('/api/user', methods=['POST'])
@login_required
@admin_required
def create_user():
    data = request.get_json()
    try:
        if not data.get('email'):
            return jsonify({'error': 'Email is required'}), 400
        if not data.get('username'):
            return jsonify({'error': 'Username is required'}), 400

        existing = User.query.filter_by(email=data['email']).first()
        if existing:
            return jsonify({'error': 'Email already exists'}), 400

        temp_password = User.generate_temp_password()

        user = User(
            username=data['username'],
            email=data['email'],
            name=data.get('name', data['username']),
            department=data.get('department', ''),
            can_manage_users=data.get('can_manage_users', False),
            can_manage_knowledge=data.get('can_manage_knowledge', False),
            active=True
        )
        user.set_password(temp_password)

        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)

        log_action(
            action='create',
            target_user_id=user.id,
            new_value=json.dumps(user.to_dict(), default=str),
            note=f"User created by {current_user.username}"
        )

        return jsonify({
            'user': user.to_dict(),
            'temp_password': temp_password
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating user: {e}")
        return jsonify({'error': str(e)}), 500


@users_bp.route('/api/user/<int:user_id>', methods=['PUT'])
@login_required
@admin_required
def update_user(user_id):
    data = request.get_json()
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        old_values = {
            'name': user.name,
            'department': user.department,
            'can_manage_users': user.can_manage_users,
            'can_manage_knowledge': user.can_manage_knowledge,
            'active': user.active
        }
        changes = []

        if 'name' in data and data['name'] != user.name:
            changes.append(f"name: {user.name} -> {data['name']}")
            user.name = data['name']
        if 'department' in data and data['department'] != user.department:
            changes.append(
                f"department: {user.department} -> {data['department']}")
            user.department = data['department']
        if 'can_manage_users' in data and data['can_manage_users'] != user.can_manage_users:
            changes.append(
                f"can_manage_users: {user.can_manage_users} -> {data['can_manage_users']}")
            user.can_manage_users = data['can_manage_users']
        if 'can_manage_knowledge' in data and data['can_manage_knowledge'] != user.can_manage_knowledge:
            changes.append(
                f"can_manage_knowledge: {user.can_manage_knowledge} -> {data['can_manage_knowledge']}")
            user.can_manage_knowledge = data['can_manage_knowledge']
        if 'is_active' in data and data['is_active'] != user.active:
            changes.append(f"active: {user.active} -> {data['is_active']}")
            user.active = data['is_active']

        if changes:
            db.session.commit()
            new_values = {
                'name': user.name,
                'department': user.department,
                'can_manage_users': user.can_manage_users,
                'can_manage_knowledge': user.can_manage_knowledge,
                'active': user.active
            }
            log_action(
                action='update',
                target_user_id=user.id,
                old_value=json.dumps(old_values, default=str),
                new_value=json.dumps(new_values, default=str),
                note="; ".join(changes)
            )

        return jsonify(user.to_dict())
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating user: {e}")
        return jsonify({'error': str(e)}), 500


@users_bp.route('/api/user/<int:user_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def reset_password(user_id):
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        temp_password = User.generate_temp_password()
        user.set_password(temp_password)
        db.session.commit()

        log_action(
            action='reset_password',
            target_user_id=user.id,
            note=f"Password reset by {current_user.username}"
        )

        return jsonify({'temp_password': temp_password})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error resetting password: {e}")
        return jsonify({'error': str(e)}), 500


@users_bp.route('/api/user/<int:user_id>/suspend', methods=['POST'])
@login_required
@admin_required
def suspend_user(user_id):
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        if user.id == current_user.id:
            return jsonify({'error': 'Cannot suspend yourself'}), 400

        old_active = user.active
        user.active = False
        db.session.commit()

        log_action(
            action='suspend',
            target_user_id=user.id,
            old_value=str(old_active),
            new_value='False',
            note=f"User suspended by {current_user.username}"
        )

        return jsonify({'status': 'suspended'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error suspending user: {e}")
        return jsonify({'error': str(e)}), 500


@users_bp.route('/api/user/<int:user_id>/reactivate', methods=['POST'])
@login_required
@admin_required
def reactivate_user(user_id):
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        old_active = user.active
        user.active = True
        db.session.commit()

        log_action(
            action='reactivate',
            target_user_id=user.id,
            old_value=str(old_active),
            new_value='True',
            note=f"User reactivated by {current_user.username}"
        )

        return jsonify({'status': 'reactivated'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error reactivating user: {e}")
        return jsonify({'error': str(e)}), 500
