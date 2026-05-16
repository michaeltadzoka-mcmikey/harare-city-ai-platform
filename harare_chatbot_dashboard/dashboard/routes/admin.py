from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from dashboard.extensions import db
from dashboard.models.user import User
from dashboard.models.audit_log import AuditLog
from dashboard.decorators import manage_users_required
import random
import string
from datetime import datetime

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/users')
@login_required
@manage_users_required
def users():
    return render_template('admin/users.html')

@bp.route('/api/users')
@login_required
@manage_users_required
def list_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '')

    query = User.query
    if search:
        query = query.filter(
            db.or_(
                User.username.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
                User.department.ilike(f'%{search}%')
            )
        )
    pagination = query.order_by(User.username).paginate(page=page, per_page=per_page, error_out=False)
    items = []
    for u in pagination.items:
        items.append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'department': u.department,
            'can_manage_users': u.can_manage_users,
            'can_manage_knowledge': u.can_manage_knowledge,
            'active': u.active,
            'last_login': u.last_login.isoformat() if u.last_login else None,
            'created_at': u.created_at.isoformat() if u.created_at else None
        })
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })

@bp.route('/api/users', methods=['POST'])
@login_required
@manage_users_required
def create_user():
    data = request.get_json()
    required = ['username', 'email']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing field: {field}'}), 400

    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400

    temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

    user = User(
        username=data['username'],
        email=data['email'],
        department=data.get('department'),
        can_manage_users=data.get('can_manage_users', False),
        can_manage_knowledge=data.get('can_manage_knowledge', False),
        active=True
    )
    user.set_password(temp_password)
    db.session.add(user)
    db.session.commit()

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='create_user',
        target_type='user',
        target_id=str(user.id),
        new_value=user.username
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({
        'success': True,
        'user_id': user.id,
        'temp_password': temp_password
    })

@bp.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
@manage_users_required
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    old_values = {c.name: getattr(user, c.name) for c in user.__table__.columns}

    if 'username' in data and data['username'] != user.username:
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 400
        user.username = data['username']
    if 'email' in data and data['email'] != user.email:
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 400
        user.email = data['email']
    if 'department' in data:
        user.department = data['department']
    if 'can_manage_users' in data:
        user.can_manage_users = data['can_manage_users']
    if 'can_manage_knowledge' in data:
        user.can_manage_knowledge = data['can_manage_knowledge']
    if 'active' in data:
        user.active = data['active']

    db.session.commit()

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='update_user',
        target_type='user',
        target_id=str(user.id),
        old_value=str(old_values),
        new_value=str({c.name: getattr(user, c.name) for c in user.__table__.columns})
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@manage_users_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    user.set_password(temp_password)
    db.session.commit()

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='reset_password',
        target_type='user',
        target_id=str(user.id)
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({'temp_password': temp_password})

@bp.route('/api/users/<int:user_id>/suspend', methods=['POST'])
@login_required
@manage_users_required
def suspend_user(user_id):
    user = User.query.get_or_404(user_id)
    user.active = not user.active
    db.session.commit()

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='toggle_suspend',
        target_type='user',
        target_id=str(user.id),
        new_value='active' if user.active else 'suspended'
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({'active': user.active})