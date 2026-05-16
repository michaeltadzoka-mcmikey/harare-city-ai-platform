import re
import json
from datetime import datetime

def parse_document_text(content):
    """
    Extract metadata and summary from a RAG compliant document.
    Returns a dict with all fields defined in the Document model,
    including new RAG 2.2 fields: topic_tags, review_cycle, cross_service_flag, authority_override.
    """
    result = {
        'title': None,
        'summary': '',
        'department': None,
        'owner_email': None,
        'valid_from': None,
        'valid_to': None,
        'locations': ['Council-wide'],
        'authority_confidence': 0.9,          # deprecated – kept for backward compatibility
        'confidence_source': None,
        'content_type': None,
        'service_area': None,
        'prerequisites': [],
        'related_documents': [],
        'topic_tags': [],
        'review_cycle': None,
        'cross_service_flag': False,
        'authority_override': None,
    }

    # Extract title from # TITLE: line
    title_match = re.search(r'^# TITLE:\s*(.*)$', content, re.MULTILINE)
    if title_match:
        result['title'] = title_match.group(1).strip()

    # Extract summary from ### Summary section (until next heading or end)
    summary_match = re.search(r'### Summary\n(.*?)(?=\n###|\Z)', content, re.DOTALL)
    if summary_match:
        result['summary'] = summary_match.group(1).strip()

    # Extract metadata block between ## METADATA_BLOCK and ## CONTENT_BLOCK
    meta_match = re.search(r'## METADATA_BLOCK\n(.*?)\n## CONTENT_BLOCK', content, re.DOTALL)
    if meta_match:
        meta_text = meta_match.group(1)
        for line in meta_text.split('\n'):
            line = line.strip()
            if not line or ':' not in line:
                continue
            key, val = line.split(':', 1)
            key = key.strip()
            val = val.strip()

            # Handle JSON fields
            if key in ['locations', 'prerequisites', 'related_documents', 'topic_tags']:
                try:
                    # Attempt to parse as JSON (allows both double and single quotes)
                    val_clean = val.replace("'", '"')
                    parsed = json.loads(val_clean)
                    if isinstance(parsed, list):
                        result[key] = parsed
                    else:
                        # If not a list, fallback to splitting by comma
                        result[key] = [x.strip() for x in val.split(',') if x.strip()]
                except (json.JSONDecodeError, TypeError):
                    # Fallback: split by comma
                    result[key] = [x.strip() for x in val.split(',') if x.strip()]
            elif key == 'authority_override':
                try:
                    val_clean = val.replace("'", '"')
                    result[key] = json.loads(val_clean)
                except:
                    result[key] = None
            elif key == 'cross_service_flag':
                result[key] = val.lower() in ['true', 'yes', '1']
            elif key in ['valid_from', 'valid_to']:
                # Store as string; caller will parse to date
                result[key] = val if val else None
            elif key == 'authority_confidence':
                try:
                    result[key] = float(val)
                except:
                    result[key] = 0.9
            else:
                # Simple string fields
                result[key] = val

    return result


def generate_type_template(content_type, service, title=None):
    """
    Generate a type-specific document skeleton with placeholder content.
    Used when creating a new document draft.
    """
    today = datetime.utcnow().date().isoformat()
    default_title = title or f"New {content_type.replace('_', ' ').title()}"
    # Create a safe document_id placeholder; actual ID will be generated on server
    doc_id_placeholder = "[AUTO-GENERATED]"

    # Common metadata prefix
    metadata_prefix = f"""# TITLE: {default_title}
# DOCUMENT_ID: {doc_id_placeholder}
# VERSION: 1

## METADATA_BLOCK
department: [Department name]
owner_email: [owner@example.com]
valid_from: {today}
valid_to: 
locations: ["Council-wide"]
authority_confidence: 0.9
confidence_source: [Source of authority, e.g., Council Resolution]
content_type: {content_type}
service_area: {service}
topic_tags: ["{service}", "keyword1", "keyword2"]
related_documents: []
prerequisites: []
review_cycle: 
cross_service_flag: false
## CONTENT_BLOCK
"""

    templates = {
        'procedure': f"""{metadata_prefix}
### Summary
Brief description of the procedure.

### Step‑by‑Step Instructions
1. First step
2. Second step
3. Third step

### Required Documents
- Document A
- Document B

### Common Questions Answered
- Q: Frequently asked question about this procedure?
- A: Answer.

## END_OF_DOCUMENT""",

        'policy': f"""{metadata_prefix}
### Summary
Brief description of the policy.

### Policy Statement
The official policy text goes here.

### Who It Applies To
- Residents of Harare
- [Other groups]

### Exceptions
- Any exceptions to the policy.

### Common Questions Answered
- Q: Frequently asked question about this policy?
- A: Answer.

## END_OF_DOCUMENT""",

        'fee_schedule': f"""{metadata_prefix}
### Summary
Summary of fees and charges.

### Fee Table
| Service | Fee (USD) | Notes |
|---------|-----------|-------|
| Item 1  | 0.00      |       |
| Item 2  | 0.00      |       |

### Payment Methods
- Cash at council offices
- Online via [link]
- Bank deposit

### Common Questions Answered
- Q: When are fees due?
- A: [Answer]

## END_OF_DOCUMENT""",

        'faq': f"""{metadata_prefix}
### Summary
Frequently asked questions about {service}.

### Questions and Answers
**Q: Question 1?**
A: Answer 1.

**Q: Question 2?**
A: Answer 2.

## END_OF_DOCUMENT""",

        'emergency': f"""{metadata_prefix}
### Summary
Emergency notice regarding {service}.

### Affected Areas
- List of suburbs or areas

### Instructions
What residents should do.

### Important Contacts
- Emergency hotline: [number]
- Council contact: [number]

## END_OF_DOCUMENT""",

        'contact_directory': f"""{metadata_prefix}
### Summary
Contact information for {service} department.

### Department Contacts
| Section | Contact Person | Phone | Email |
|---------|----------------|-------|-------|
|         |                |       |       |
|         |                |       |       |

### Common Questions Answered
- Q: How do I reach the manager?
- A: [Answer]

## END_OF_DOCUMENT"""
    }

    return templates.get(content_type, f"""{metadata_prefix}
### Summary
[Summary]

### Content
[Main content goes here]

## END_OF_DOCUMENT""")