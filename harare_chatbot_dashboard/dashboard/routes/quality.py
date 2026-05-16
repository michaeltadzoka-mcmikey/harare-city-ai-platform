from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from dashboard.extensions import db
from dashboard.models.document import Document
from dashboard.decorators import manage_knowledge_required
from sqlalchemy import func

bp = Blueprint('quality', __name__, url_prefix='/documents/api/quality')

@bp.route('/stats')
@login_required
def get_stats():
    """Return aggregate stats for document quality."""
    total = Document.query.count()
    
    # Count documents with topic_tags present and non-empty
    with_tags = Document.query.filter(
        Document.topic_tags.isnot(None),
        Document.topic_tags != '[]'
    ).count()
    missing_tags = total - with_tags

    # Count documents with related_documents present and non-empty
    with_related = Document.query.filter(
        Document.related_documents.isnot(None),
        Document.related_documents != '[]'
    ).count()
    missing_related = total - with_related

    # Count documents with authority_override set
    with_overrides = Document.query.filter(Document.authority_override.isnot(None)).count()

    # Count documents missing prerequisites (optional but flagged)
    missing_prereqs = Document.query.filter(
        db.or_(
            Document.prerequisites.is_(None),
            Document.prerequisites == '[]'
        )
    ).count()

    complete_pct = (with_tags / total * 100) if total > 0 else 0

    return jsonify({
        'total': total,
        'complete_pct': round(complete_pct, 1),
        'missing_tags': missing_tags,
        'missing_related': missing_related,
        'missing_prereqs': missing_prereqs,
        'with_overrides': with_overrides
    })

@bp.route('/missing-tags')
@login_required
def list_missing_tags():
    """List documents missing topic_tags."""
    docs = Document.query.filter(
        db.or_(
            Document.topic_tags.is_(None),
            Document.topic_tags == '[]'
        )
    ).limit(100).all()
    return jsonify([{
        'id': d.id,
        'document_id': d.document_id,
        'title': d.title,
        'service': d.service_area,
        'content_type': d.content_type
    } for d in docs])

@bp.route('/missing-related')
@login_required
def list_missing_related():
    """List documents missing related_documents."""
    docs = Document.query.filter(
        db.or_(
            Document.related_documents.is_(None),
            Document.related_documents == '[]'
        )
    ).limit(100).all()
    return jsonify([{
        'id': d.id,
        'document_id': d.document_id,
        'title': d.title,
        'service': d.service_area,
        'content_type': d.content_type
    } for d in docs])

@bp.route('/missing-prereqs')
@login_required
def list_missing_prereqs():
    """List documents missing prerequisites."""
    docs = Document.query.filter(
        db.or_(
            Document.prerequisites.is_(None),
            Document.prerequisites == '[]'
        )
    ).limit(100).all()
    return jsonify([{
        'id': d.id,
        'document_id': d.document_id,
        'title': d.title,
        'service': d.service_area
    } for d in docs])

@bp.route('/overrides')
@login_required
def list_authority_overrides():
    """List documents with authority overrides."""
    docs = Document.query.filter(Document.authority_override.isnot(None)).limit(100).all()
    return jsonify([{
        'id': d.id,
        'document_id': d.document_id,
        'title': d.title,
        'service': d.service_area,
        'content_type': d.content_type,
        'override': d.authority_override
    } for d in docs])

@bp.route('/bulk-add-tags', methods=['POST'])
@login_required
@manage_knowledge_required
def bulk_add_tags():
    """Bulk add a tag to multiple documents."""
    data = request.get_json()
    doc_ids = data.get('doc_ids', [])
    tag = data.get('tag')
    if not tag or not doc_ids:
        return jsonify({'error': 'Tag and document IDs required'}), 400

    docs = Document.query.filter(Document.id.in_(doc_ids)).all()
    for doc in docs:
        if not doc.topic_tags:
            doc.topic_tags = []
        if tag not in doc.topic_tags:
            doc.topic_tags.append(tag)
    db.session.commit()
    return jsonify({'success': True, 'count': len(docs)})

@bp.route('/bulk-add-related', methods=['POST'])
@login_required
@manage_knowledge_required
def bulk_add_related():
    """Bulk add a related document ID to multiple documents."""
    data = request.get_json()
    doc_ids = data.get('doc_ids', [])
    related_id = data.get('related_id')
    if not related_id or not doc_ids:
        return jsonify({'error': 'Related document ID and document IDs required'}), 400

    docs = Document.query.filter(Document.id.in_(doc_ids)).all()
    for doc in docs:
        if not doc.related_documents:
            doc.related_documents = []
        if related_id not in doc.related_documents:
            doc.related_documents.append(related_id)
    db.session.commit()
    return jsonify({'success': True, 'count': len(docs)})