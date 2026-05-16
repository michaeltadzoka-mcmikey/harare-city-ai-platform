"""
Local document validator for dashboard.
Replaces RAG's validation for faster, offline validation.
"""

import json
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Union
from dashboard.models.document import Document
from dashboard.utils.document_parser import parse_document_text
from flask import current_app

def validate_document_local(
    doc_data: Union[Dict[str, Any], Document],
    exclude_doc_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Validate a document (draft or active) against RAG 2.2 rules.
    Returns dict with keys: valid, errors, overlap_detected, overlap_with.
    """
    errors = []
    # Extract metadata and content
    if isinstance(doc_data, Document):
        # It's a model instance
        metadata = {
            'document_id': doc_data.document_id,
            'title': doc_data.title,
            'version': doc_data.version,
            'department': doc_data.department,
            'owner_email': doc_data.owner_email,
            'valid_from': doc_data.valid_from.isoformat() if doc_data.valid_from else None,
            'valid_to': doc_data.valid_to.isoformat() if doc_data.valid_to else None,
            'content_type': doc_data.content_type,
            'service_area': doc_data.service_area,
            'locations': doc_data.locations,
            'authority_confidence': doc_data.authority_confidence,
            'confidence_source': doc_data.confidence_source,
            'prerequisites': doc_data.prerequisites,
            'related_documents': doc_data.related_documents,
            'topic_tags': doc_data.topic_tags,
            'review_cycle': doc_data.review_cycle,
            'cross_service_flag': doc_data.cross_service_flag,
            'authority_override': doc_data.authority_override,
        }
        content = doc_data.content
    else:
        # Dict from frontend
        content = doc_data.get('content', '')
        # If content is present, parse it to get metadata; otherwise use provided fields
        if content:
            parsed = parse_document_text(content)
            metadata = {
                'document_id': doc_data.get('document_id') or parsed.get('document_id'),
                'title': parsed.get('title'),
                'version': int(parsed.get('version', 1)),
                'department': parsed.get('department'),
                'owner_email': parsed.get('owner_email'),
                'valid_from': parsed.get('valid_from'),
                'valid_to': parsed.get('valid_to'),
                'content_type': parsed.get('content_type'),
                'service_area': parsed.get('service_area'),
                'locations': parsed.get('locations', []),
                'authority_confidence': parsed.get('authority_confidence', 0.9),
                'confidence_source': parsed.get('confidence_source'),
                'prerequisites': parsed.get('prerequisites', []),
                'related_documents': parsed.get('related_documents', []),
                'topic_tags': parsed.get('topic_tags', []),
                'review_cycle': parsed.get('review_cycle'),
                'cross_service_flag': parsed.get('cross_service_flag', False),
                'authority_override': parsed.get('authority_override'),
            }
        else:
            # No content, use provided fields
            metadata = {
                'document_id': doc_data.get('document_id'),
                'title': doc_data.get('title'),
                'version': doc_data.get('version', 1),
                'department': doc_data.get('department'),
                'owner_email': doc_data.get('owner_email'),
                'valid_from': doc_data.get('valid_from'),
                'valid_to': doc_data.get('valid_to'),
                'content_type': doc_data.get('content_type'),
                'service_area': doc_data.get('service_area'),
                'locations': doc_data.get('locations', []),
                'authority_confidence': doc_data.get('authority_confidence', 0.9),
                'confidence_source': doc_data.get('confidence_source'),
                'prerequisites': doc_data.get('prerequisites', []),
                'related_documents': doc_data.get('related_documents', []),
                'topic_tags': doc_data.get('topic_tags', []),
                'review_cycle': doc_data.get('review_cycle'),
                'cross_service_flag': doc_data.get('cross_service_flag', False),
                'authority_override': doc_data.get('authority_override'),
            }

    # Required fields (from config)
    required_fields = current_app.config.get('REQUIRED_METADATA_FIELDS', [
        "document_id", "title", "version", "department", "owner_email",
        "valid_from", "valid_to", "content_type", "service_area", "locations", "topic_tags"
    ])
    for field in required_fields:
        value = metadata.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"Missing required field: {field}")

    # Data type checks
    try:
        version = int(metadata['version'])
    except (TypeError, ValueError):
        errors.append("Version must be an integer")

    # Dates
    valid_from = None
    if metadata.get('valid_from'):
        try:
            valid_from = date.fromisoformat(metadata['valid_from'])
        except ValueError:
            errors.append("valid_from must be in ISO format (YYYY-MM-DD)")
    else:
        errors.append("valid_from is required")

    valid_to = None
    if metadata.get('valid_to'):
        try:
            valid_to = date.fromisoformat(metadata['valid_to'])
        except ValueError:
            errors.append("valid_to must be in ISO format (YYYY-MM-DD)")
    else:
        errors.append("valid_to is required")

    # Ensure valid_to >= valid_from
    if valid_from and valid_to and valid_to < valid_from:
        errors.append("valid_to must be >= valid_from")

    # Content type check
    content_type = metadata.get('content_type')
    allowed_content_types = current_app.config.get('CONTENT_TYPES', [
        'procedure', 'policy', 'fee_schedule', 'faq', 'emergency', 'contact_directory',
        'service_update', 'pinned_override'
    ])
    if content_type and content_type not in allowed_content_types:
        errors.append(f"Invalid content_type: {content_type}. Allowed: {', '.join(allowed_content_types)}")

    # Service area – no longer validated against a fixed list; only check it's not empty
    service_area = metadata.get('service_area')
    if not service_area:
        errors.append("service_area is required")
    # (no further validation – any name is allowed)

    # Locations must be list or "Council-wide"
    locations = metadata.get('locations')
    if not isinstance(locations, list) and locations != "Council-wide":
        errors.append("locations must be a list or 'Council-wide'")

    # Topic tags must be list
    topic_tags = metadata.get('topic_tags')
    if not isinstance(topic_tags, list):
        # If it's a string, try to parse as JSON first, then fallback to split by commas
        if isinstance(topic_tags, str):
            try:
                # Try JSON parsing (e.g., ["tag1", "tag2"])
                parsed = json.loads(topic_tags)
                if isinstance(parsed, list):
                    metadata['topic_tags'] = parsed
                else:
                    # Not a list, split by commas
                    metadata['topic_tags'] = [t.strip() for t in topic_tags.split(',') if t.strip()]
            except (json.JSONDecodeError, TypeError):
                # Split by commas
                metadata['topic_tags'] = [t.strip() for t in topic_tags.split(',') if t.strip()]
            topic_tags = metadata['topic_tags']
        else:
            errors.append("topic_tags must be a list")

    # Overlap detection (only for active documents, and exclude current document if provided)
    overlap_detected = False
    overlap_with = None
    if content_type and service_area and valid_from and valid_to:
        # Find active documents with same service_area and content_type
        query = Document.query.filter(
            Document.status == 'active',
            Document.service_area == service_area,
            Document.content_type == content_type
        )
        if exclude_doc_id:
            query = query.filter(Document.id != exclude_doc_id)
        existing_docs = query.all()

        for existing in existing_docs:
            # Existing document validity
            existing_valid_from = existing.valid_from
            existing_valid_to = existing.valid_to or date.max
            # Overlap if windows intersect
            if valid_from <= existing_valid_to and valid_to >= existing_valid_from:
                overlap_detected = True
                overlap_with = existing.document_id
                break

    # If there are errors, overall is invalid
    valid = len(errors) == 0 and not overlap_detected

    return {
        'valid': valid,
        'errors': errors,
        'overlap_detected': overlap_detected,
        'overlap_with': overlap_with
    }