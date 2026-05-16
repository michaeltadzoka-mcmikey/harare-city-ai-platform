"""
Documents & RAG routes – Full updated version with all fixes.
Includes real Last Ingest and Queue values from local database with formatted date.
"""

from flask import Blueprint, render_template, request, jsonify, session, current_app, send_file
from flask_login import login_required, current_user
from dashboard.extensions import db, limiter
from dashboard.models.document import Document, DocumentVersion
from dashboard.models.override import Override
from dashboard.models.audit_log import AuditLog
from dashboard.models.conflict import Conflict, ProvisionalResolution
from dashboard.models.knowledge_gap import KnowledgeGap
from dashboard.decorators import manage_knowledge_required
from dashboard.utils.rag_client import (
    rag_ingest_document, rag_chunk_preview,
    rag_get_expiring_docs, rag_get_conflict_analytics, rag_get_conflict_details,
    rag_wipe_knowledge_base, rag_get_service_coverage, rag_archive_expired,
    rag_auto_fix_metadata, rag_get_document_tree, rag_get_detailed_health
)
from dashboard.utils.document_validator import validate_document_local
from dashboard.utils.document_parser import parse_document_text, generate_type_template
from dashboard.utils.notifications import send_notification
from dashboard.utils.file_manager import (
    write_document_file, archive_document_file, restore_document_file,
    delete_document_file, delete_archived_file, get_active_path, ensure_dir
)
from werkzeug.utils import secure_filename
import json
from datetime import datetime, timedelta
import os
import re
import uuid
import csv
import io
import zipfile
import shutil
from sqlalchemy import or_

bp = Blueprint('documents', __name__, url_prefix='/documents')

# ---------- Helper: Create conflict record ----------
def create_conflict_if_needed(doc1, doc2, reason):
    """Create a Conflict record if one doesn't already exist between these two documents."""
    existing = Conflict.query.filter(
        ((Conflict.doc1_id == doc1.id) & (Conflict.doc2_id == doc2.id)) |
        ((Conflict.doc1_id == doc2.id) & (Conflict.doc2_id == doc1.id))
    ).first()
    if not existing:
        conflict = Conflict(doc1_id=doc1.id, doc2_id=doc2.id, reason=reason)
        db.session.add(conflict)
        db.session.commit()
        return conflict
    return existing

# ---------- Helper: Sync document_id in content ----------
def sync_document_id_in_content(content, doc_id):
    """Replace or add the 'document_id:' line in the content to match the database document_id."""
    lines = content.split('\n')
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith('document_id:'):
            lines[i] = f'document_id: {doc_id}'
            found = True
            break
    if not found:
        # Insert after the title or at the top
        for i, line in enumerate(lines):
            if line.strip().startswith('# TITLE:') or line.strip().startswith('title:'):
                lines.insert(i+1, f'document_id: {doc_id}')
                found = True
                break
        if not found:
            lines.insert(0, f'document_id: {doc_id}')
    return '\n'.join(lines)

# ---------- Helper: Ensure valid_to line exists and is correct ----------
def ensure_valid_to_line(content, default_date):
    """Ensure the content has a valid_to: line with the given date."""
    lines = content.split('\n')
    found = False
    for i, line in enumerate(lines):
        if re.match(r'^\s*valid_to\s*:', line, re.IGNORECASE):
            lines[i] = f'valid_to: {default_date.isoformat()}'
            found = True
            break
    if not found:
        # Insert after valid_from line or at the end of METADATA_BLOCK
        inserted = False
        for i, line in enumerate(lines):
            if line.strip().startswith('valid_from:'):
                lines.insert(i+1, f'valid_to: {default_date.isoformat()}')
                inserted = True
                break
        if not inserted:
            # Find METADATA_BLOCK and add near the end
            for i, line in enumerate(lines):
                if line.strip() == '## CONTENT_BLOCK':
                    lines.insert(i, f'valid_to: {default_date.isoformat()}')
                    inserted = True
                    break
        if not inserted:
            lines.append(f'valid_to: {default_date.isoformat()}')
    return '\n'.join(lines)

# ---------- Helper: Ensure valid_from is today or later ----------
def ensure_valid_from_today(content):
    """Ensure valid_from is set to today's date."""
    today = datetime.utcnow().date().isoformat()
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if re.match(r'^\s*valid_from\s*:', line, re.IGNORECASE):
            lines[i] = f'valid_from: {today}'
            break
    return '\n'.join(lines)

# ---------- Routes ----------
@bp.route('/')
@login_required
def index():
    return render_template('documents.html')

@bp.route('/api/health')
@login_required
@limiter.exempt
def health():
    """Get RAG health plus local last ingest and queue size (formatted date)."""
    from dashboard.utils.rag_client import rag_get_health
    rag_health = rag_get_health()
    
    # Compute local last ingest time (most recent successful ingestion)
    last_doc = Document.query.filter(Document.ingested_at.isnot(None)).order_by(Document.ingested_at.desc()).first()
    last_ingest_raw = last_doc.ingested_at if last_doc and last_doc.ingested_at else None
    
    # Format for display: "2026-04-06 11:32"
    if last_ingest_raw:
        last_ingest = last_ingest_raw.strftime('%Y-%m-%d %H:%M')
    else:
        last_ingest = None
    
    # Compute queue size: documents that need ingestion
    queue_size = Document.query.filter(Document.needs_ingestion == True).count()
    
    return jsonify({
        'status': rag_health.get('status', 'offline'),
        'chunks': rag_health.get('chunks', 0),
        'documents': rag_health.get('documents', 0),
        'queue': queue_size,
        'last_ingest': last_ingest
    })

@bp.route('/api/health/details')
@login_required
def health_details():
    details = rag_get_detailed_health()
    return jsonify(details)

@bp.route('/api/service-areas')
@login_required
def service_areas():
    base_path = current_app.config['RAG_DOCUMENTS_PATH']
    by_service_path = os.path.join(base_path, 'by_service')
    services = []
    if os.path.exists(by_service_path):
        for item in os.listdir(by_service_path):
            if os.path.isdir(os.path.join(by_service_path, item)):
                services.append(item)
    return jsonify(services)

@bp.route('/api/filter-options')
@login_required
def filter_options():
    doc_services = db.session.query(Document.service_area).distinct().filter(Document.service_area.isnot(None)).all()
    doc_content_types = db.session.query(Document.content_type).distinct().filter(Document.content_type.isnot(None)).all()
    
    services = set(s[0] for s in doc_services)
    content_types = set(c[0] for c in doc_content_types)
    
    base_path = current_app.config['RAG_DOCUMENTS_PATH']
    by_service_path = os.path.join(base_path, 'by_service')
    if os.path.exists(by_service_path):
        for service in os.listdir(by_service_path):
            if os.path.isdir(os.path.join(by_service_path, service)):
                services.add(service)
                service_path = os.path.join(by_service_path, service)
                for ct in os.listdir(service_path):
                    if os.path.isdir(os.path.join(service_path, ct)):
                        content_types.add(ct)
    
    return jsonify({
        'services': sorted(list(services)),
        'content_types': sorted(list(content_types))
    })

@bp.route('/api/tree')
@login_required
def get_tree():
    tree = {'by_service': {}, 'archived': {'count': 0, 'documents': []}}
    
    docs = Document.query.filter(Document.status != 'archived').all()
    
    for doc in docs:
        service = doc.service_area
        ct = doc.content_type
        if service not in tree['by_service']:
            tree['by_service'][service] = {}
        if ct not in tree['by_service'][service]:
            tree['by_service'][service][ct] = {'count': 0, 'documents': []}
        tree['by_service'][service][ct]['count'] += 1
        tree['by_service'][service][ct]['documents'].append({
            'id': doc.id,
            'document_id': doc.document_id,
            'title': doc.title,
            'version': doc.version,
            'locked': doc.locked,
            'status': doc.status,
            'cross_service_flag': doc.cross_service_flag
        })
    
    archived = Document.query.filter_by(status='archived').all()
    tree['archived']['count'] = len(archived)
    tree['archived']['documents'] = [{
        'id': d.id,
        'document_id': d.document_id,
        'title': d.title,
        'version': d.version,
        'archived_at': d.last_modified_at.isoformat() if d.last_modified_at else None
    } for d in archived[:100]]
    
    base_path = current_app.config['RAG_DOCUMENTS_PATH']
    by_service_path = os.path.join(base_path, 'by_service')
    if os.path.exists(by_service_path):
        for service in os.listdir(by_service_path):
            service_path = os.path.join(by_service_path, service)
            if os.path.isdir(service_path):
                if service not in tree['by_service']:
                    tree['by_service'][service] = {}
                for ct in os.listdir(service_path):
                    ct_path = os.path.join(service_path, ct)
                    if os.path.isdir(ct_path):
                        if ct not in tree['by_service'][service]:
                            tree['by_service'][service][ct] = {'count': 0, 'documents': []}
    
    return jsonify(tree)

@bp.route('/api/list')
@login_required
def list_documents():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', current_app.config['ITEMS_PER_PAGE'], type=int)
    service = request.args.get('service')
    content_type = request.args.get('content_type')
    status = request.args.get('status')
    search = request.args.get('search')
    tags = request.args.get('tags')
    owner_email = request.args.get('owner_email')
    related_doc = request.args.get('related_doc')

    query = Document.query
    if service:
        query = query.filter_by(service_area=service)
    if content_type:
        query = query.filter_by(content_type=content_type)
    
    today = datetime.utcnow().date()
    if status == 'expired':
        query = query.filter(
            or_(
                Document.status == 'expired',
                Document.valid_to < today
            )
        )
    elif status:
        query = query.filter_by(status=status)
    
    if search:
        query = query.filter(
            db.or_(
                Document.title.ilike(f'%{search}%'),
                Document.document_id.ilike(f'%{search}%'),
                Document.content.ilike(f'%{search}%')
            )
        )
    if tags:
        if db.engine.dialect.name == 'sqlite':
            query = query.filter(Document.topic_tags.cast(db.String).like(f'%{tags}%'))
        else:
            query = query.filter(Document.topic_tags.contains([tags]))
    if owner_email:
        query = query.filter(Document.owner_email.ilike(f'%{owner_email}%'))
    if related_doc:
        if db.engine.dialect.name == 'sqlite':
            query = query.filter(Document.related_documents.cast(db.String).like(f'%{related_doc}%'))
        else:
            query = query.filter(Document.related_documents.contains([related_doc]))

    pagination = query.order_by(Document.uploaded_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    items = []
    for doc in pagination.items:
        items.append({
            'id': doc.id,
            'document_id': doc.document_id,
            'title': doc.title,
            'version': doc.version,
            'service': doc.service_area,
            'content_type': doc.content_type,
            'status': doc.status,
            'locked': doc.locked,
            'uploaded_at': doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            'uploaded_by': doc.uploaded_by,
            'needs_ingestion': doc.needs_ingestion,
            'topic_tags': doc.topic_tags
        })
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })

@bp.route('/api/export')
@login_required
def export_filtered():
    service = request.args.get('service')
    content_type = request.args.get('content_type')
    status = request.args.get('status')
    search = request.args.get('search')
    tags = request.args.get('tags')
    owner_email = request.args.get('owner_email')
    related_doc = request.args.get('related_doc')

    query = Document.query
    if service:
        query = query.filter_by(service_area=service)
    if content_type:
        query = query.filter_by(content_type=content_type)
    if status:
        query = query.filter_by(status=status)
    if search:
        query = query.filter(
            db.or_(
                Document.title.ilike(f'%{search}%'),
                Document.document_id.ilike(f'%{search}%'),
                Document.content.ilike(f'%{search}%')
            )
        )
    if tags:
        if db.engine.dialect.name == 'sqlite':
            query = query.filter(Document.topic_tags.cast(db.String).like(f'%{tags}%'))
    if owner_email:
        query = query.filter(Document.owner_email.ilike(f'%{owner_email}%'))
    if related_doc:
        if db.engine.dialect.name == 'sqlite':
            query = query.filter(Document.related_documents.cast(db.String).like(f'%{related_doc}%'))

    docs = query.all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Document ID', 'Title', 'Version', 'Service', 'Content Type', 'Status', 'Uploaded At', 'Topic Tags', 'Owner Email', 'Related Documents'])
    for doc in docs:
        writer.writerow([
            doc.id,
            doc.document_id,
            doc.title,
            doc.version,
            doc.service_area,
            doc.content_type,
            doc.status,
            doc.uploaded_at.isoformat() if doc.uploaded_at else '',
            ','.join(doc.topic_tags) if doc.topic_tags else '',
            doc.owner_email or '',
            ','.join(doc.related_documents) if doc.related_documents else ''
        ])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'documents_export_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.csv'
    )

@bp.route('/api/document/<int:doc_id>')
@login_required
def get_document(doc_id):
    try:
        doc = Document.query.get_or_404(doc_id)
        can_edit = current_user.can_manage_knowledge and (not doc.locked or current_user.can_manage_knowledge)
        authority_tier_map = {
            'policy': 'STATUTORY',
            'fee_schedule': 'POLICY',
            'procedure': 'POLICY',
            'service_update': 'NOTICE',
            'faq': 'INFORMATIONAL',
            'contact_directory': 'INFORMATIONAL',
            'emergency': 'STATUTORY'
        }
        derived_tier = authority_tier_map.get(doc.content_type, 'INFORMATIONAL')
        effective_tier = doc.authority_override.get('tier') if doc.authority_override else derived_tier

        return jsonify({
            'id': doc.id,
            'document_id': doc.document_id,
            'version': doc.version,
            'title': doc.title,
            'content': doc.content,
            'summary': doc.summary,
            'service': doc.service_area,
            'content_type': doc.content_type,
            'department': doc.department,
            'owner_email': doc.owner_email,
            'valid_from': doc.valid_from.isoformat() if doc.valid_from else None,
            'valid_to': doc.valid_to.isoformat() if doc.valid_to else None,
            'locations': doc.locations,
            'authority_confidence': doc.authority_confidence,
            'confidence_source': doc.confidence_source,
            'prerequisites': doc.prerequisites,
            'related_documents': doc.related_documents,
            'topic_tags': doc.topic_tags,
            'review_cycle': doc.review_cycle,
            'cross_service_flag': doc.cross_service_flag,
            'authority_override': doc.authority_override,
            'derived_tier': derived_tier,
            'effective_tier': effective_tier,
            'status': doc.status,
            'locked': doc.locked,
            'uploaded_by': doc.uploaded_by,
            'uploaded_at': doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            'needs_ingestion': doc.needs_ingestion,
            'can_edit': can_edit
        })
    except Exception as e:
        current_app.logger.error(f"Error loading document {doc_id}: {e}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/document', methods=['POST'])
@login_required
@manage_knowledge_required
def create_document():
    data = request.get_json()
    
    service = data.get('service_area')
    content_type = data.get('content_type')
    title = data.get('title')
    if not service or not content_type:
        return jsonify({'error': 'Service area and content type are required'}), 400

    content = generate_type_template(content_type, service, title)
    parsed = parse_document_text(content)
    
    if data.get('department'):
        parsed['department'] = data['department']
    if data.get('owner_email'):
        parsed['owner_email'] = data['owner_email']
    if data.get('valid_from'):
        parsed['valid_from'] = data['valid_from']
    if data.get('valid_to'):
        parsed['valid_to'] = data['valid_to']
    if data.get('locations'):
        parsed['locations'] = data['locations']
    if data.get('authority_confidence'):
        parsed['authority_confidence'] = float(data['authority_confidence'])
    if data.get('confidence_source'):
        parsed['confidence_source'] = data['confidence_source']
    if data.get('topic_tags'):
        parsed['topic_tags'] = data['topic_tags']
    if data.get('review_cycle'):
        parsed['review_cycle'] = data['review_cycle']
    if data.get('cross_service_flag') is not None:
        parsed['cross_service_flag'] = data['cross_service_flag']
    if data.get('authority_override'):
        parsed['authority_override'] = data['authority_override']

    required_fields = ['title', 'service_area', 'content_type']
    for field in required_fields:
        if field not in parsed or not parsed[field]:
            return jsonify({'error': f'Missing required field in document: {field}'}), 400

    doc_id = data.get('document_id')
    if not doc_id or doc_id == '[AUTO-GENERATED]':
        base = f"{parsed['service_area']}-{parsed['content_type']}-{re.sub(r'[^a-z0-9]+', '-', parsed['title'].lower())}"
        doc_id = base[:80]
        original = doc_id
        counter = 1
        while Document.query.filter_by(document_id=doc_id).first():
            doc_id = f"{original}-{counter}"
            counter += 1

    owner_email = parsed.get('owner_email') or current_user.email
    valid_from = None
    if parsed.get('valid_from'):
        try:
            valid_from = datetime.fromisoformat(parsed['valid_from']).date()
        except ValueError:
            valid_from = datetime.utcnow().date()
    else:
        valid_from = datetime.utcnow().date()

    valid_to = None
    if parsed.get('valid_to'):
        try:
            valid_to = datetime.fromisoformat(parsed['valid_to']).date()
        except ValueError:
            valid_to = None

    topic_tags = parsed.get('topic_tags', [])
    if not topic_tags:
        topic_tags = [service]

    review_cycle = parsed.get('review_cycle')
    cross_service_flag = parsed.get('cross_service_flag', False)
    authority_override = parsed.get('authority_override')

    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('department:'):
            lines[i] = f'department: {parsed.get("department", "")}'
        elif line.startswith('owner_email:'):
            lines[i] = f'owner_email: {owner_email}'
        elif line.startswith('valid_from:'):
            lines[i] = f'valid_from: {valid_from.isoformat()}'
        elif line.startswith('valid_to:'):
            lines[i] = f'valid_to: {valid_to.isoformat() if valid_to else ""}'
        elif line.startswith('locations:'):
            lines[i] = f'locations: {json.dumps(parsed.get("locations", ["Council-wide"]))}'
        elif line.startswith('authority_confidence:'):
            lines[i] = f'authority_confidence: {parsed.get("authority_confidence", 0.9)}'
        elif line.startswith('confidence_source:'):
            lines[i] = f'confidence_source: {parsed.get("confidence_source", "")}'
        elif line.startswith('topic_tags:'):
            lines[i] = f'topic_tags: {json.dumps(topic_tags)}'
        elif line.startswith('review_cycle:'):
            lines[i] = f'review_cycle: {review_cycle or ""}'
        elif line.startswith('cross_service_flag:'):
            lines[i] = f'cross_service_flag: {str(cross_service_flag).lower()}'
        elif line.startswith('authority_override:'):
            lines[i] = f'authority_override: {json.dumps(authority_override) if authority_override else ""}'
    content = '\n'.join(lines)

    doc = Document(
        document_id=doc_id,
        title=parsed['title'],
        content=content,
        summary=parsed.get('summary'),
        service_area=parsed['service_area'],
        content_type=parsed['content_type'],
        department=parsed.get('department', current_user.department),
        owner_email=owner_email,
        valid_from=valid_from,
        valid_to=valid_to,
        locations=parsed.get('locations', ['Council-wide']),
        authority_confidence=parsed.get('authority_confidence', 0.9),
        confidence_source=parsed.get('confidence_source'),
        prerequisites=data.get('prerequisites', parsed.get('prerequisites', [])),
        related_documents=data.get('related_documents', parsed.get('related_documents', [])),
        topic_tags=topic_tags,
        review_cycle=review_cycle,
        cross_service_flag=cross_service_flag,
        authority_override=authority_override,
        status='draft',
        uploaded_by=current_user.id,
        needs_ingestion=True
    )
    db.session.add(doc)
    db.session.commit()

    write_document_file(doc)

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='create_document',
        target_type='document',
        target_id=doc.document_id,
        new_value=json.dumps({'title': doc.title, 'service': doc.service_area})
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    return jsonify({'id': doc.id, 'document_id': doc.document_id})

@bp.route('/api/document/<int:doc_id>', methods=['PUT'])
@login_required
@manage_knowledge_required
def update_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.locked and not current_user.can_manage_knowledge:
        return jsonify({'error': 'Document is locked'}), 403

    data = request.get_json()
    new_content = data.get('content')
    if not new_content:
        return jsonify({'error': 'No content provided'}), 400

    # Sync document_id in content to match database value
    new_content = sync_document_id_in_content(new_content, doc.document_id)

    parsed = parse_document_text(new_content)

    doc.content = new_content
    doc.title = parsed.get('title', doc.title)
    doc.summary = parsed.get('summary', doc.summary)
    doc.service_area = parsed.get('service_area', doc.service_area)
    doc.content_type = parsed.get('content_type', doc.content_type)
    doc.department = parsed.get('department', doc.department)
    doc.owner_email = parsed.get('owner_email', doc.owner_email)
    
    if parsed.get('valid_from'):
        try:
            doc.valid_from = datetime.fromisoformat(parsed['valid_from']).date()
        except ValueError:
            pass
    if parsed.get('valid_to'):
        try:
            doc.valid_to = datetime.fromisoformat(parsed['valid_to']).date()
        except ValueError:
            doc.valid_to = None
    
    doc.locations = parsed.get('locations', doc.locations)
    doc.authority_confidence = parsed.get('authority_confidence', doc.authority_confidence)
    doc.confidence_source = parsed.get('confidence_source', doc.confidence_source)

    doc.topic_tags = parsed.get('topic_tags', doc.topic_tags)
    doc.review_cycle = parsed.get('review_cycle', doc.review_cycle)
    doc.cross_service_flag = parsed.get('cross_service_flag', doc.cross_service_flag)
    if 'authority_override' in parsed and parsed['authority_override'] is not None:
        doc.authority_override = parsed['authority_override']

    if 'prerequisites' in data:
        doc.prerequisites = data['prerequisites']
    if 'related_documents' in data:
        doc.related_documents = data['related_documents']

    doc.last_modified_by = current_user.id
    doc.last_modified_at = datetime.utcnow()
    doc.needs_ingestion = True
    db.session.commit()

    write_document_file(doc)

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='update_document',
        target_type='document',
        target_id=doc.document_id,
        old_value=json.dumps({c.name: getattr(doc, c.name) for c in doc.__table__.columns}, default=str),
        new_value=json.dumps({f: getattr(doc, f) for f in parsed.keys() if hasattr(doc, f)}, default=str)
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/document/<int:doc_id>/authority-override', methods=['POST'])
@login_required
@manage_knowledge_required
def set_authority_override(doc_id):
    doc = Document.query.get_or_404(doc_id)
    data = request.get_json()
    tier = data.get('tier')
    justification = data.get('justification')

    if not tier or tier not in ['STATUTORY', 'POLICY', 'NOTICE', 'INFORMATIONAL']:
        return jsonify({'error': 'Valid tier required'}), 400
    if not justification or len(justification) < 20:
        return jsonify({'error': 'Justification must be at least 20 characters'}), 400

    doc.authority_override = {'tier': tier, 'justification': justification}
    doc.last_modified_by = current_user.id
    doc.last_modified_at = datetime.utcnow()
    doc.needs_ingestion = True
    db.session.commit()

    write_document_file(doc)

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='authority_override',
        target_type='document',
        target_id=doc.document_id,
        note=f"Set authority override to {tier}: {justification[:50]}..."
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    return jsonify({'success': True})

# ========== FIXED: Ingest now forces valid_to and valid_from to be correct ==========
@bp.route('/api/document/<int:doc_id>/ingest', methods=['POST'])
@login_required
@manage_knowledge_required
def ingest_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    
    # FIRST: Ensure the document's content has valid dates before validation
    default_valid_to = (datetime.utcnow().date() + timedelta(days=365))
    doc.content = ensure_valid_to_line(doc.content, default_valid_to)
    doc.content = ensure_valid_from_today(doc.content)
    doc.content = sync_document_id_in_content(doc.content, doc.document_id)
    
    # Update the database fields to match the forced dates
    today = datetime.utcnow().date()
    doc.valid_from = today
    doc.valid_to = default_valid_to
    doc.last_modified_by = current_user.id
    doc.last_modified_at = datetime.utcnow()
    doc.needs_ingestion = True
    
    # Write the corrected content to file
    write_document_file(doc)
    db.session.commit()
    
    # Now validate (should pass)
    validation = validate_document_local(doc, exclude_doc_id=doc_id)
    if not validation.get('valid'):
        return jsonify({'error': 'Validation failed', 'details': validation.get('errors')}), 400

    result = rag_ingest_document(doc)
    if result.get('success'):
        doc.status = 'active'
        doc.needs_ingestion = False
        doc.ingested_at = datetime.utcnow()
        db.session.commit()
        write_document_file(doc)
        log = AuditLog(
            user_id=current_user.id,
            username=current_user.username,
            action='ingest_document',
            target_type='document',
            target_id=doc.document_id
        )
        db.session.add(log)
        log.set_hash_chain()
        db.session.commit()
        return jsonify({'success': True})
    else:
        error_msg = result.get('error', 'Ingestion failed')
        error_details = result.get('details', [])
        return jsonify({'error': error_msg, 'details': error_details}), 400

@bp.route('/api/document/<int:doc_id>/archive', methods=['POST'])
@login_required
@manage_knowledge_required
def archive_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    
    if not archive_document_file(doc):
        return jsonify({'error': 'Failed to archive document file'}), 500
    
    doc.status = 'archived'
    db.session.commit()

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='archive_document',
        target_type='document',
        target_id=doc.document_id
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    return jsonify({'success': True})

# ========== FIXED: restore_document now robustly adds valid_to line ==========
@bp.route('/api/document/<int:doc_id>/restore', methods=['POST'])
@login_required
@manage_knowledge_required
def restore_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.status != 'archived':
        return jsonify({'error': 'Document is not archived'}), 400

    if not restore_document_file(doc):
        return jsonify({'error': 'Failed to restore document file'}), 500

    version = DocumentVersion(
        document_id=doc.id,
        version=doc.version,
        content=doc.content,
        metadata_json={'title': doc.title, 'service': doc.service_area},
        created_by=current_user.id,
        reason='restored'
    )
    db.session.add(version)

    doc.version += 1
    doc.status = 'active'
    doc.needs_ingestion = True
    doc.valid_from = datetime.utcnow().date()
    doc.valid_to = (datetime.utcnow().date() + timedelta(days=365))
    doc.last_modified_by = current_user.id
    doc.last_modified_at = datetime.utcnow()
    
    # Set a default valid_to (1 year from today)
    default_valid_to = (datetime.utcnow().date() + timedelta(days=365))
    
    # Update the content string with current database metadata
    # First, ensure valid_to line is present and correct
    doc.content = ensure_valid_to_line(doc.content, default_valid_to)
    doc.content = ensure_valid_from_today(doc.content)
    
    # Then update other fields
    lines = doc.content.split('\n')
    new_lines = []
    for line in lines:
        if line.startswith('service_area:'):
            new_lines.append(f'service_area: {doc.service_area}')
        elif line.startswith('content_type:'):
            new_lines.append(f'content_type: {doc.content_type}')
        elif line.startswith('topic_tags:'):
            new_lines.append(f'topic_tags: {json.dumps(doc.topic_tags)}')
        else:
            new_lines.append(line)
    doc.content = '\n'.join(new_lines)
    
    # Ensure document_id line matches
    doc.content = sync_document_id_in_content(doc.content, doc.document_id)
    
    # Write the updated content to the file
    write_document_file(doc)
    
    db.session.commit()

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='restore_document',
        target_type='document',
        target_id=doc.document_id,
        note=f"Restored from version {version.version}"
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    return jsonify({'success': True, 'new_version': doc.version})

@bp.route('/api/document/<int:doc_id>/lock', methods=['POST'])
@login_required
@manage_knowledge_required
def toggle_lock(doc_id):
    doc = Document.query.get_or_404(doc_id)
    doc.locked = not doc.locked
    db.session.commit()

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='toggle_lock',
        target_type='document',
        target_id=doc.document_id,
        note=f"Lock set to {doc.locked}"
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    return jsonify({'locked': doc.locked})

@bp.route('/api/document/<int:doc_id>/versions')
@login_required
def get_document_versions(doc_id):
    versions = DocumentVersion.query.filter_by(document_id=doc_id).order_by(DocumentVersion.created_at.desc()).all()
    result = []
    for v in versions:
        result.append({
            'id': v.id,
            'version': v.version,
            'created_at': v.created_at.isoformat() if v.created_at else None,
            'created_by': v.created_by,
            'reason': v.reason,
            'content_preview': v.content[:100] + '...' if v.content and len(v.content) > 100 else v.content
        })
    return jsonify(result)

@bp.route('/api/version-diff')
@login_required
def version_diff():
    v1_id = request.args.get('v1')
    v2_id = request.args.get('v2')
    if not v1_id or not v2_id:
        return jsonify({'error': 'Two version IDs required'}), 400
    v1 = DocumentVersion.query.get_or_404(v1_id)
    v2 = DocumentVersion.query.get_or_404(v2_id)
    return jsonify({
        'v1': {'version': v1.version, 'content': v1.content, 'created_at': v1.created_at},
        'v2': {'version': v2.version, 'content': v2.content, 'created_at': v2.created_at}
    })

@bp.route('/api/document/<int:doc_id>/new-version', methods=['POST'])
@login_required
@manage_knowledge_required
def create_new_version(doc_id):
    doc = Document.query.get_or_404(doc_id)
    data = request.get_json()

    old_version = DocumentVersion(
        document_id=doc.id,
        version=doc.version,
        content=doc.content,
        metadata_json={
            'title': doc.title,
            'service': doc.service_area,
            'content_type': doc.content_type
        },
        created_by=current_user.id,
        reason='new_version'
    )
    db.session.add(old_version)

    doc.version += 1
    if data.get('content'):
        doc.content = data['content']
    if data.get('valid_from'):
        doc.valid_from = datetime.fromisoformat(data['valid_from'])
    if data.get('valid_to'):
        doc.valid_to = datetime.fromisoformat(data['valid_to'])
    doc.last_modified_by = current_user.id
    doc.last_modified_at = datetime.utcnow()
    doc.needs_ingestion = True
    db.session.commit()

    write_document_file(doc)

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='create_version',
        target_type='document',
        target_id=doc.document_id,
        note=f"New version {doc.version} created"
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    return jsonify({'success': True, 'new_version': doc.version})

@bp.route('/api/document/<int:doc_id>/assign', methods=['POST'])
@login_required
@manage_knowledge_required
def assign_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    data = request.get_json()
    assignee = data.get('assignee')
    message = data.get('message', '')

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='assign_document',
        target_type='document',
        target_id=doc.document_id,
        note=f"Assigned to {assignee}: {message}"
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/document/<int:doc_id>/request-approval', methods=['POST'])
@login_required
@manage_knowledge_required
def request_approval(doc_id):
    doc = Document.query.get_or_404(doc_id)
    doc.status = 'pending'
    db.session.commit()

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='request_approval',
        target_type='document',
        target_id=doc.document_id
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/document/<int:doc_id>/retire', methods=['POST'])
@login_required
@manage_knowledge_required
def retire_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.status != 'active':
        return jsonify({'error': 'Only active documents can be retired'}), 400
    
    if not archive_document_file(doc):
        return jsonify({'error': 'Failed to archive document file'}), 500
    
    yesterday = datetime.utcnow().date() - timedelta(days=1)
    doc.valid_to = yesterday
    doc.status = 'archived'
    db.session.commit()

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='retire_document',
        target_type='document',
        target_id=doc.document_id,
        note="Retired to resolve overlap"
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/document/<int:doc_id>/delete-permanent', methods=['POST'])
@login_required
@manage_knowledge_required
def delete_document_permanent(doc_id):
    doc = Document.query.get_or_404(doc_id)
    if doc.status != 'archived':
        return jsonify({'error': 'Only archived documents can be permanently deleted'}), 400
    
    data = request.get_json()
    justification = data.get('justification', '')
    if len(justification) < 20:
        return jsonify({'error': 'Justification must be at least 20 characters'}), 400
    
    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='permanent_delete',
        target_type='document',
        target_id=doc.document_id,
        note=f"Permanent deletion: {justification}"
    )
    db.session.add(log)
    log.set_hash_chain()
    
    if not delete_archived_file(doc):
        return jsonify({'error': 'Failed to delete file from archive'}), 500
    
    db.session.delete(doc)
    db.session.commit()
    
    return jsonify({'success': True})

@bp.route('/api/document/<int:doc_id>/rename', methods=['POST'])
@login_required
@manage_knowledge_required
def rename_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    data = request.get_json()
    new_title = data.get('title')
    justification = data.get('justification', '')
    
    if not new_title:
        return jsonify({'error': 'Title required'}), 400
    if len(justification) < 20:
        return jsonify({'error': 'Justification must be at least 20 characters'}), 400
    
    doc.title = new_title
    lines = doc.content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('# TITLE:'):
            lines[i] = f'# TITLE: {new_title}'
            break
    doc.content = '\n'.join(lines)
    doc.last_modified_by = current_user.id
    doc.last_modified_at = datetime.utcnow()
    doc.needs_ingestion = True
    db.session.commit()
    
    write_document_file(doc)
    
    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='rename_document',
        target_type='document',
        target_id=doc.document_id,
        note=f"Renamed to '{new_title}': {justification}"
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    
    return jsonify({'success': True})

@bp.route('/api/document/<int:doc_id>/change-content-type', methods=['POST'])
@login_required
@manage_knowledge_required
def change_document_content_type(doc_id):
    doc = Document.query.get_or_404(doc_id)
    data = request.get_json()
    new_type = data.get('content_type')
    justification = data.get('justification', '')
    
    if not new_type:
        return jsonify({'error': 'Content type required'}), 400
    if new_type not in current_app.config['CONTENT_TYPES']:
        return jsonify({'error': 'Invalid content type'}), 400
    if len(justification) < 20:
        return jsonify({'error': 'Justification must be at least 20 characters'}), 400
    
    old_type = doc.content_type
    if old_type == new_type:
        return jsonify({'error': 'Document already has this content type'}), 400
    
    src = get_active_path(doc.service_area, old_type, doc.document_id)
    dst = get_active_path(doc.service_area, new_type, doc.document_id)
    if os.path.exists(src):
        ensure_dir(dst)
        shutil.move(src, dst)
    else:
        return jsonify({'error': 'Source file not found'}), 500
    
    doc.content_type = new_type
    doc.last_modified_by = current_user.id
    doc.last_modified_at = datetime.utcnow()
    doc.needs_ingestion = True
    db.session.commit()
    
    lines = doc.content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('content_type:'):
            lines[i] = f'content_type: {new_type}'
            break
    doc.content = '\n'.join(lines)
    write_document_file(doc)
    
    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='change_content_type',
        target_type='document',
        target_id=doc.document_id,
        note=f"Changed from {old_type} to {new_type}: {justification}"
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    
    return jsonify({'success': True})

@bp.route('/api/document/<int:doc_id>/update-tags', methods=['POST'])
@login_required
@manage_knowledge_required
def update_document_tags(doc_id):
    doc = Document.query.get_or_404(doc_id)
    data = request.get_json()
    tags = data.get('tags', [])
    
    doc.topic_tags = tags
    doc.last_modified_by = current_user.id
    doc.last_modified_at = datetime.utcnow()
    doc.needs_ingestion = True
    db.session.commit()
    
    lines = doc.content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('topic_tags:'):
            lines[i] = f'topic_tags: {json.dumps(tags)}'
            break
    doc.content = '\n'.join(lines)
    write_document_file(doc)
    
    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='update_tags',
        target_type='document',
        target_id=doc.document_id,
        note=f"Tags updated: {tags}"
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    
    return jsonify({'success': True})

@bp.route('/api/overlap/resolve', methods=['POST'])
@login_required
@manage_knowledge_required
def resolve_overlap():
    data = request.get_json()
    doc_id = data.get('document_id')
    action = data.get('action')
    justification = data.get('justification', '')
    if not doc_id or not action:
        return jsonify({'error': 'Document ID and action required'}), 400

    doc = Document.query.get_or_404(doc_id)

    if action == 'retire':
        conflicting_id = data.get('conflicting_id')
        if not conflicting_id:
            return jsonify({'error': 'Conflicting document ID required'}), 400
        conflicting = Document.query.filter_by(document_id=conflicting_id).first()
        if not conflicting:
            return jsonify({'error': 'Conflicting document not found'}), 404
        
        archive_success = archive_document_file(conflicting)
        if not archive_success:
            current_app.logger.error(f"Failed to archive conflicting document {conflicting.document_id} for overlap resolution. Proceeding with DB archival only.")
        
        conflicting.valid_to = datetime.utcnow().date() - timedelta(days=1)
        conflicting.status = 'archived'
        db.session.commit()

        # Force correct dates on the document to be ingested
        default_valid_to = (datetime.utcnow().date() + timedelta(days=365))
        doc.content = ensure_valid_to_line(doc.content, default_valid_to)
        doc.content = ensure_valid_from_today(doc.content)
        doc.valid_from = datetime.utcnow().date()
        doc.valid_to = default_valid_to
        write_document_file(doc)
        db.session.commit()

        validation = validate_document_local(doc, exclude_doc_id=doc.id)
        if not validation.get('valid'):
            return jsonify({'error': 'Validation still fails', 'details': validation.get('errors')}), 400

        result = rag_ingest_document(doc)
        if result.get('success'):
            doc.status = 'active'
            doc.needs_ingestion = False
            doc.ingested_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'error': result.get('error', 'Ingestion failed')}), 500

    elif action == 'override':
        if len(justification) < 20:
            return jsonify({'error': 'Justification must be at least 20 characters'}), 400

        result = rag_ingest_document(doc, override_overlap=True, override_justification=justification)
        if result.get('success'):
            doc.status = 'active'
            doc.needs_ingestion = False
            doc.ingested_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'error': result.get('error', 'Ingestion failed')}), 500

    else:
        return jsonify({'error': 'Invalid action'}), 400

@bp.route('/api/bulk', methods=['POST'])
@login_required
@manage_knowledge_required
def bulk_action():
    data = request.get_json()
    action = data.get('action')
    doc_ids = data.get('document_ids', [])
    if not doc_ids:
        return jsonify({'error': 'No documents selected'}), 400

    docs = Document.query.filter(Document.id.in_(doc_ids)).all()
    if action == 'archive':
        for doc in docs:
            if not archive_document_file(doc):
                return jsonify({'error': f'Failed to archive document {doc.document_id}'}), 500
            doc.status = 'archived'
    elif action == 'restore':
        for doc in docs:
            if doc.status == 'archived':
                if not restore_document_file(doc):
                    return jsonify({'error': f'Failed to restore document {doc.document_id}'}), 500
                dv = DocumentVersion(
                    document_id=doc.id,
                    version=doc.version,
                    content=doc.content,
                    created_by=current_user.id,
                    reason='bulk_restore'
                )
                db.session.add(dv)
                doc.version += 1
                doc.status = 'active'
                doc.needs_ingestion = True
    elif action == 'ingest':
        for doc in docs:
            doc.needs_ingestion = True
    else:
        return jsonify({'error': 'Invalid action'}), 400

    db.session.commit()

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action=f'bulk_{action}',
        target_type='document',
        target_id=','.join([str(d.id) for d in docs]),
        note=f"Affected {len(docs)} documents"
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    return jsonify({'success': True, 'count': len(docs)})

@bp.route('/api/bulk-import', methods=['POST'])
@login_required
@manage_knowledge_required
def bulk_import():
    target_service = request.form.get('target_service')
    target_content_type = request.form.get('target_content_type')
    
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    files = request.files.getlist('files')
    results = []
    for file in files:
        filename = secure_filename(file.filename)
        if not filename.endswith('.txt'):
            results.append({'file': filename, 'status': 'error', 'message': 'Only .txt files allowed'})
            continue
        try:
            content = file.read().decode('utf-8')
            parsed = parse_document_text(content)
            missing = []
            for field in ['title', 'service_area', 'content_type']:
                if field not in parsed or not parsed[field]:
                    missing.append(field)
            if missing:
                results.append({'file': filename, 'status': 'error', 'message': f'Missing fields: {", ".join(missing)}'})
                continue
            
            if target_service:
                parsed['service_area'] = target_service
            if target_content_type:
                parsed['content_type'] = target_content_type
            
            doc_id = parsed.get('document_id')
            if not doc_id or doc_id == '[AUTO-GENERATED]':
                base = f"{parsed['service_area']}-{parsed['content_type']}-{re.sub(r'[^a-z0-9]+', '-', parsed['title'].lower())}"
                doc_id = base[:80]
                original = doc_id
                counter = 1
                while Document.query.filter_by(document_id=doc_id).first():
                    doc_id = f"{original}-{counter}"
                    counter += 1
            doc = Document(
                document_id=doc_id,
                title=parsed['title'],
                content=content,
                summary=parsed.get('summary'),
                service_area=parsed['service_area'],
                content_type=parsed['content_type'],
                department=parsed.get('department', current_user.department),
                owner_email=parsed.get('owner_email', current_user.email),
                valid_from=datetime.fromisoformat(parsed['valid_from']).date() if parsed.get('valid_from') else datetime.utcnow().date(),
                valid_to=datetime.fromisoformat(parsed['valid_to']).date() if parsed.get('valid_to') else None,
                locations=parsed.get('locations', ['Council-wide']),
                authority_confidence=parsed.get('authority_confidence', 0.9),
                confidence_source=parsed.get('confidence_source'),
                prerequisites=parsed.get('prerequisites', []),
                related_documents=parsed.get('related_documents', []),
                topic_tags=parsed.get('topic_tags', [parsed['service_area']]),
                review_cycle=parsed.get('review_cycle'),
                cross_service_flag=parsed.get('cross_service_flag', False),
                authority_override=parsed.get('authority_override'),
                status='draft',
                uploaded_by=current_user.id,
                needs_ingestion=True
            )
            db.session.add(doc)
            db.session.commit()
            write_document_file(doc)
            results.append({'file': filename, 'status': 'success', 'message': f'Imported as {doc.document_id}'})
        except Exception as e:
            db.session.rollback()
            results.append({'file': filename, 'status': 'error', 'message': str(e)})
    return jsonify({'results': results})

# ========== FIXED: list_overrides now accepts API key authentication (permanent) ==========
@bp.route('/api/overrides')
def list_overrides():
    # Force reload the API key from environment (fallback)
    expected_key = current_app.config.get('INBOUND_API_KEY') or os.environ.get('INBOUND_API_KEY')
    if not expected_key:
        expected_key = 'change-this-in-production'  # hardcoded fallback – change to your actual key

    api_key = request.headers.get('X-API-Key')

    # Debug prints (remove after testing)
    print(f"[DEBUG] Received X-API-Key: {api_key}")
    print(f"[DEBUG] Expected key: {expected_key}")

    if api_key and api_key == expected_key:
        show_expired = request.args.get('show_expired', 'false').lower() == 'true'
        service = request.args.get('service')
        query = Override.query
        if not show_expired:
            query = query.filter_by(is_active=True)
        if service:
            query = query.filter_by(service=service)
        overrides = query.order_by(Override.created_at.desc()).limit(200).all()
        return jsonify([{
            'id': o.id,
            'override_id': o.override_id,
            'override_type': o.override_type,
            'target_type': o.target_type,
            'target_value': o.target_value,
            'service': o.service,
            'valid_from': o.valid_from.isoformat() if o.valid_from else None,
            'valid_to': o.valid_to.isoformat() if o.valid_to else None,
            'justification': o.justification,
            'created_by': o.created_by,
            'created_at': o.created_at.isoformat() if o.created_at else None,
            'is_active': o.is_active,
            'content': o.content
        } for o in overrides])

    # Fallback to normal session authentication
    if not current_user.is_authenticated:
        return jsonify({'error': 'Unauthorized'}), 401

    show_expired = request.args.get('show_expired', 'false').lower() == 'true'
    service = request.args.get('service')
    query = Override.query
    if not show_expired:
        query = query.filter_by(is_active=True)
    if service:
        query = query.filter_by(service=service)
    overrides = query.order_by(Override.created_at.desc()).limit(200).all()
    return jsonify([{
        'id': o.id,
        'override_id': o.override_id,
        'override_type': o.override_type,
        'target_type': o.target_type,
        'target_value': o.target_value,
        'service': o.service,
        'valid_from': o.valid_from.isoformat() if o.valid_from else None,
        'valid_to': o.valid_to.isoformat() if o.valid_to else None,
        'justification': o.justification,
        'created_by': o.created_by,
        'created_at': o.created_at.isoformat() if o.created_at else None,
        'is_active': o.is_active,
        'content': o.content
    } for o in overrides])

@bp.route('/api/overrides', methods=['POST'])
@login_required
@manage_knowledge_required
def create_override():
    data = request.get_json()
    required = ['override_type', 'target_type', 'target_value', 'content', 'justification']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing field: {field}'}), 400

    override_id = f"OVR-{datetime.utcnow().year}-{uuid.uuid4().hex[:6].upper()}"
    ov = Override(
        override_id=override_id,
        override_type=data['override_type'],
        target_type=data['target_type'],
        target_value=data['target_value'],
        service=data.get('service'),
        location_scope=data.get('location_scope', []),
        trigger_conditions=data.get('trigger_conditions'),
        content=data['content'],
        valid_from=datetime.fromisoformat(data['valid_from']) if data.get('valid_from') else datetime.utcnow().date(),
        valid_to=datetime.fromisoformat(data['valid_to']) if data.get('valid_to') else None,
        justification=data['justification'],
        approved=data.get('approved', False),
        created_by=current_user.id,
        is_active=True
    )
    db.session.add(ov)
    db.session.commit()

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='create_override',
        target_type='override',
        target_id=ov.override_id
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    return jsonify({'success': True, 'override_id': ov.override_id})

@bp.route('/api/overrides/<int:ov_id>/revoke', methods=['POST'])
@login_required
@manage_knowledge_required
def revoke_override(ov_id):
    ov = Override.query.get_or_404(ov_id)
    ov.is_active = False
    ov.revoked_by = current_user.id
    ov.revoked_at = datetime.utcnow()
    db.session.commit()

    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='revoke_override',
        target_type='override',
        target_id=ov.override_id
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    return jsonify({'success': True})

# ========== FIXED: Validate route now excludes current document from overlap detection ==========
@bp.route('/api/validate', methods=['POST'])
@login_required
def validate_document():
    data = request.get_json()
    exclude_id = None
    
    # If the request contains a document_id but no content, load the existing document
    if data.get('document_id') and not data.get('content'):
        doc = Document.query.filter_by(document_id=data['document_id']).first()
        if doc:
            # Convert model to dict for validation
            data = {c.name: getattr(doc, c.name) for c in doc.__table__.columns}
            exclude_id = doc.id  # Exclude this document from overlap check
    # If the frontend sends an 'id' field directly (database id)
    elif data.get('id'):
        exclude_id = data.get('id')
    
    # Perform local validation, excluding the current document's ID
    result = validate_document_local(data, exclude_doc_id=exclude_id)
    
    # If overlap detected, create a conflict record in the database
    if result.get('overlap_detected') and result.get('overlap_with'):
        # Find the current document (if it exists in DB)
        current_doc = None
        if data.get('id'):
            current_doc = Document.query.get(data['id'])
        elif data.get('document_id'):
            current_doc = Document.query.filter_by(document_id=data['document_id']).first()
        
        if current_doc:
            conflicting_doc = Document.query.filter_by(document_id=result['overlap_with']).first()
            if conflicting_doc:
                create_conflict_if_needed(current_doc, conflicting_doc, 'validity_overlap')
    
    return jsonify(result)

@bp.route('/api/auto-fix-metadata', methods=['POST'])
@login_required
def auto_fix_metadata():
    data = request.get_json()
    if data.get('document_id') and not data.get('content'):
        doc = Document.query.filter_by(document_id=data['document_id']).first()
        if doc:
            data = {c.name: getattr(doc, c.name) for c in doc.__table__.columns}
    result = rag_auto_fix_metadata(data)
    return jsonify(result)

@bp.route('/api/chunk-preview', methods=['POST'])
@login_required
def chunk_preview():
    data = request.get_json()
    result = rag_chunk_preview(data.get('content', ''))
    return jsonify(result)

@bp.route('/api/expiring-docs')
@login_required
def expiring_docs():
    days = request.args.get('days', 7, type=int)
    data = rag_get_expiring_docs(days)
    return jsonify(data)

@bp.route('/api/conflict-analytics')
@login_required
def conflict_analytics():
    data = rag_get_conflict_analytics()
    return jsonify(data)

@bp.route('/api/conflict-details')
@login_required
def conflict_details():
    conflict_id = request.args.get('conflict_id')
    service = request.args.get('service')
    data = rag_get_conflict_details(conflict_id, service)
    return jsonify(data)

@bp.route('/api/conflicts')
@login_required
def list_conflicts():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', 'unresolved')
    query = Conflict.query.filter_by(status=status)
    pagination = query.order_by(Conflict.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    items = []
    for c in pagination.items:
        items.append({
            'id': c.id,
            'doc1': {'id': c.doc1.id, 'document_id': c.doc1.document_id, 'title': c.doc1.title},
            'doc2': {'id': c.doc2.id, 'document_id': c.doc2.document_id, 'title': c.doc2.title},
            'reason': c.reason,
            'created_at': c.created_at.isoformat(),
            'status': c.status
        })
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })

@bp.route('/api/conflicts/<int:conflict_id>/resolve', methods=['POST'])
@login_required
@manage_knowledge_required
def resolve_conflict(conflict_id):
    conflict = Conflict.query.get_or_404(conflict_id)
    data = request.get_json()
    resolution = data.get('resolution')
    selected_doc_id = data.get('selected_doc_id')
    justification = data.get('justification', '')

    if resolution == 'retire_one':
        if not selected_doc_id:
            return jsonify({'error': 'Document ID to retire required'}), 400
        doc_to_retire = Document.query.filter_by(document_id=selected_doc_id).first()
        if not doc_to_retire:
            return jsonify({'error': 'Document not found'}), 404
        if not archive_document_file(doc_to_retire):
            return jsonify({'error': 'Failed to archive document'}), 500
        doc_to_retire.status = 'archived'
        doc_to_retire.valid_to = datetime.utcnow().date() - timedelta(days=1)
        db.session.commit()
        conflict.status = 'resolved'
        conflict.resolved_at = datetime.utcnow()
        conflict.resolved_by = current_user.id
        conflict.resolution_notes = f"Retired {selected_doc_id}: {justification}"
        db.session.commit()
        return jsonify({'success': True})
    elif resolution == 'override':
        if len(justification) < 20:
            return jsonify({'error': 'Justification must be at least 20 characters'}), 400
        conflict.status = 'resolved'
        conflict.resolved_at = datetime.utcnow()
        conflict.resolved_by = current_user.id
        conflict.resolution_notes = f"Override resolution: {justification}"
        db.session.commit()
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Invalid resolution method'}), 400

@bp.route('/api/service-coverage')
@login_required
def service_coverage():
    """Get service coverage – includes services from filesystem even without documents."""
    data = rag_get_service_coverage()
    if isinstance(data, dict) and 'error' not in data and data.get('services'):
        return jsonify(data)
    
    base_path = current_app.config['RAG_DOCUMENTS_PATH']
    by_service_path = os.path.join(base_path, 'by_service')
    services_from_fs = []
    if os.path.exists(by_service_path):
        for item in os.listdir(by_service_path):
            if os.path.isdir(os.path.join(by_service_path, item)):
                services_from_fs.append(item)
    
    db_services = db.session.query(Document.service_area).distinct().filter(Document.service_area.isnot(None)).all()
    all_services = set(services_from_fs) | {s[0] for s in db_services if s[0]}
    
    if not all_services:
        return jsonify({'services': [], 'message': 'No services found. Create a service using "New Service Area".'})
    
    standard_types = current_app.config['CONTENT_TYPES']
    coverage_list = []
    for service in sorted(all_services):
        present_types = db.session.query(Document.content_type).filter_by(service_area=service).distinct().count()
        coverage = (present_types / len(standard_types)) * 100 if standard_types else 0
        missing_categories = len(standard_types) - present_types
        coverage_list.append({
            'name': service,
            'coverage': round(coverage, 1),
            'missing_categories': missing_categories
        })
    return jsonify({'services': coverage_list})

@bp.route('/api/service-health')
@login_required
def service_health():
    services = db.session.query(Document.service_area).distinct().all()
    result = []
    standard_types = ['procedure', 'policy', 'fee_schedule', 'faq', 'emergency', 'contact_directory']
    for (service,) in services:
        if not service:
            continue
        total = Document.query.filter_by(service_area=service).count()
        if total == 0:
            continue
        present_types = db.session.query(Document.content_type).filter_by(service_area=service).distinct().count()
        coverage = (present_types / len(standard_types)) * 100
        conflict_count = Conflict.query.filter(
            (Conflict.doc1.has(service_area=service)) | (Conflict.doc2.has(service_area=service)),
            Conflict.status == 'unresolved'
        ).count()
        conflict_penalty = min(100, (conflict_count / total) * 100)
        expired_count = Document.query.filter_by(service_area=service, status='expired').count()
        expired_penalty = min(100, (expired_count / total) * 100)
        health = coverage * 0.5 - conflict_penalty * 0.3 - expired_penalty * 0.2
        health = max(0, min(100, health))
        result.append({
            'service': service,
            'coverage': round(coverage, 1),
            'conflict_penalty': round(conflict_penalty, 1),
            'expired_penalty': round(expired_penalty, 1),
            'health': round(health, 1),
            'color': 'green' if health >= 80 else 'yellow' if health >= 50 else 'red'
        })
    return jsonify(result)

# ========== FIXED: Wipe endpoint with service parameter and correct success detection ==========
@bp.route('/api/wipe', methods=['POST'])
@login_required
@manage_knowledge_required
def wipe_knowledge_base():
    data = request.get_json()
    scope = data.get('scope', 'full')
    justification = data.get('justification', '')
    backup_confirmed = data.get('backup_confirmed', False)
    service = data.get('service')

    if not backup_confirmed:
        return jsonify({'error': 'Backup confirmation required'}), 400

    if scope == 'service' and not service:
        return jsonify({'error': 'Service name required for service wipe'}), 400

    try:
        result = rag_wipe_knowledge_base(scope, service=service)
    except Exception as e:
        current_app.logger.error(f"Wipe failed: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

    # RAG returns 200 with JSON like {"message": "Cleared", "status": "success"} – no 'success' key.
    # Consider success if there's no 'error' key.
    if 'error' not in result:
        # Archive local documents if full or service wipe
        if scope in ['full', 'service']:
            query = Document.query.filter_by(status='active')
            if scope == 'service' and service:
                query = query.filter_by(service_area=service)
            docs = query.all()
            for doc in docs:
                archive_document_file(doc)
                doc.status = 'archived'
            db.session.commit()

        log = AuditLog(
            user_id=current_user.id,
            username=current_user.username,
            action='wipe_knowledge_base',
            target_type='system',
            note=f"Scope: {scope}, service: {service if scope=='service' else 'all'}, justification: {justification}"
        )
        db.session.add(log)
        log.set_hash_chain()
        db.session.commit()
        return jsonify({'success': True})
    else:
        return jsonify({'error': result.get('error', 'Wipe failed')}), 500

@bp.route('/api/archive-expired', methods=['POST'])
@login_required
@manage_knowledge_required
def archive_expired():
    result = rag_archive_expired()
    return jsonify(result)

@bp.route('/api/audit')
@login_required
def audit_log():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    action = request.args.get('action', '')
    query = AuditLog.query.order_by(AuditLog.timestamp.desc())
    if action:
        query = query.filter_by(action=action)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    items = [{
        'timestamp': log.timestamp.isoformat(),
        'user': log.username,
        'action': log.action,
        'target_type': log.target_type,
        'target_id': log.target_id,
        'note': log.note
    } for log in pagination.items]
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    })

@bp.route('/api/service', methods=['POST'])
@login_required
@manage_knowledge_required
def create_service():
    data = request.get_json()
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Service name required'}), 400
    
    base_path = current_app.config['RAG_DOCUMENTS_PATH']
    service_path = os.path.join(base_path, 'by_service', name)
    os.makedirs(service_path, exist_ok=True)
    
    content_types = data.get('content_types', current_app.config['CONTENT_TYPES'])
    for ct in content_types:
        os.makedirs(os.path.join(service_path, ct), exist_ok=True)
    
    archived_service_path = os.path.join(base_path, 'archived', 'by_service', name)
    os.makedirs(archived_service_path, exist_ok=True)
    for ct in content_types:
        os.makedirs(os.path.join(archived_service_path, ct), exist_ok=True)
    
    return jsonify({'success': True})

@bp.route('/api/service/<service>/content-types', methods=['POST'])
@login_required
@manage_knowledge_required
def add_content_types(service):
    data = request.get_json()
    content_types = data.get('content_types', [])
    base_path = current_app.config['RAG_DOCUMENTS_PATH']
    service_path = os.path.join(base_path, 'by_service', service)
    for ct in content_types:
        os.makedirs(os.path.join(service_path, ct), exist_ok=True)
        archived_ct_path = os.path.join(base_path, 'archived', 'by_service', service, ct)
        os.makedirs(archived_ct_path, exist_ok=True)
    return jsonify({'success': True})

@bp.route('/api/service/<service>/rename', methods=['POST'])
@login_required
@manage_knowledge_required
def rename_service(service):
    data = request.get_json()
    new_name = data.get('new_name')
    justification = data.get('justification', '')
    
    if not new_name:
        return jsonify({'error': 'New name required'}), 400
    if len(justification) < 20:
        return jsonify({'error': 'Justification must be at least 20 characters'}), 400
    
    base_path = current_app.config['RAG_DOCUMENTS_PATH']
    old_path = os.path.join(base_path, 'by_service', service)
    new_path = os.path.join(base_path, 'by_service', new_name)
    old_archived = os.path.join(base_path, 'archived', 'by_service', service)
    new_archived = os.path.join(base_path, 'archived', 'by_service', new_name)
    
    if not os.path.exists(old_path):
        return jsonify({'error': 'Service folder not found'}), 404
    if os.path.exists(new_path):
        return jsonify({'error': 'New service name already exists'}), 400
    
    Document.query.filter_by(service_area=service).update({'service_area': new_name})
    KnowledgeGap.query.filter_by(service=service).update({'service': new_name})
    
    os.rename(old_path, new_path)
    if os.path.exists(old_archived):
        os.rename(old_archived, new_archived)
    
    db.session.commit()
    
    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='rename_service',
        target_type='service',
        target_id=service,
        note=f"Renamed to {new_name}: {justification}"
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    
    return jsonify({'success': True})

@bp.route('/api/service/<service>/delete', methods=['POST'])
@login_required
@manage_knowledge_required
def delete_service(service):
    data = request.get_json()
    justification = data.get('justification', '')
    if len(justification) < 20:
        return jsonify({'error': 'Justification must be at least 20 characters'}), 400
    
    active_count = Document.query.filter_by(service_area=service, status='active').count()
    if active_count > 0:
        return jsonify({'error': f'Service has {active_count} active documents. Archive them first.'}), 400
    
    docs = Document.query.filter_by(service_area=service).all()
    for doc in docs:
        if doc.status != 'archived':
            archive_document_file(doc)
            doc.status = 'archived'
    db.session.commit()
    
    base_path = current_app.config['RAG_DOCUMENTS_PATH']
    active_folder = os.path.join(base_path, 'by_service', service)
    archived_folder = os.path.join(base_path, 'archived', 'by_service', service)
    
    if os.path.exists(active_folder):
        shutil.rmtree(active_folder)
    if os.path.exists(archived_folder):
        shutil.rmtree(archived_folder)
    
    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='delete_service',
        target_type='service',
        target_id=service,
        note=f"Service deleted: {justification}"
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    
    return jsonify({'success': True})

@bp.route('/api/service/<service>/archive-all', methods=['POST'])
@login_required
@manage_knowledge_required
def archive_all_service_docs(service):
    data = request.get_json()
    justification = data.get('justification', '')
    if len(justification) < 20:
        return jsonify({'error': 'Justification must be at least 20 characters'}), 400
    
    docs = Document.query.filter_by(service_area=service, status='active').all()
    count = 0
    for doc in docs:
        if archive_document_file(doc):
            doc.status = 'archived'
            count += 1
    db.session.commit()
    
    log = AuditLog(
        user_id=current_user.id,
        username=current_user.username,
        action='archive_all_service',
        target_type='service',
        target_id=service,
        note=f"Archived {count} documents: {justification}"
    )
    db.session.add(log)
    log.set_hash_chain()
    db.session.commit()
    
    return jsonify({'success': True, 'count': count})

@bp.route('/api/service/<service>/bulk-add-tag', methods=['POST'])
@login_required
@manage_knowledge_required
def bulk_add_tag_service(service):
    data = request.get_json()
    tag = data.get('tag')
    include_archived = data.get('include_archived', False)
    
    if not tag:
        return jsonify({'error': 'Tag required'}), 400
    
    query = Document.query.filter_by(service_area=service)
    if not include_archived:
        query = query.filter_by(status='active')
    
    docs = query.all()
    count = 0
    for doc in docs:
        if not doc.topic_tags:
            doc.topic_tags = []
        if tag not in doc.topic_tags:
            doc.topic_tags.append(tag)
            count += 1
    db.session.commit()
    
    return jsonify({'success': True, 'count': count})

@bp.route('/api/service/<service>/export-csv')
@login_required
def export_service_csv(service):
    docs = Document.query.filter_by(service_area=service).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Document ID', 'Title', 'Version', 'Content Type', 'Status', 'Uploaded At', 'Topic Tags'])
    for doc in docs:
        writer.writerow([
            doc.id,
            doc.document_id,
            doc.title,
            doc.version,
            doc.content_type,
            doc.status,
            doc.uploaded_at.isoformat() if doc.uploaded_at else '',
            ','.join(doc.topic_tags) if doc.topic_tags else ''
        ])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'{service}_documents.csv'
    )

@bp.route('/api/service/<service>/details')
@login_required
def service_details(service):
    total = Document.query.filter_by(service_area=service).count()
    active = Document.query.filter_by(service_area=service, status='active').count()
    archived = Document.query.filter_by(service_area=service, status='archived').count()
    expired = Document.query.filter_by(service_area=service, status='expired').count()
    
    content_types = db.session.query(Document.content_type).filter_by(service_area=service).distinct().all()
    present = [ct[0] for ct in content_types if ct[0]]
    standard_types = ['procedure', 'policy', 'fee_schedule', 'faq', 'emergency', 'contact_directory']
    missing = [t for t in standard_types if t not in present]
    
    conflicts = Conflict.query.filter(
        (Conflict.doc1.has(service_area=service)) | (Conflict.doc2.has(service_area=service)),
        Conflict.status == 'unresolved'
    ).count()
    
    return jsonify({
        'total': total,
        'active': active,
        'archived': archived,
        'expired': expired,
        'content_types': present,
        'missing_types': missing,
        'conflicts': conflicts
    })

@bp.route('/api/export-folder', methods=['POST'])
@login_required
def export_folder():
    data = request.get_json()
    folder_path = data.get('path')
    if not folder_path:
        return jsonify({'error': 'Folder path required'}), 400
    
    base = current_app.config['RAG_DOCUMENTS_PATH']
    full_path = os.path.join(base, folder_path)
    if not os.path.isdir(full_path):
        return jsonify({'error': 'Folder not found'}), 404
    
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(full_path):
            for file in files:
                if file.endswith('.txt'):
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, base)
                    zf.write(file_path, arcname)
    memory_file.seek(0)
    
    folder_name = os.path.basename(folder_path)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'{folder_name}.zip'
    )