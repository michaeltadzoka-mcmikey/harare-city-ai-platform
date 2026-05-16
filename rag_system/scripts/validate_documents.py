#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import config
from app.core.loader import DocumentLoader
from app.core.ingestion_validator import IngestionValidator

def main():
    print("📋 Document Validation Report (v2.2)")
    print("=" * 70)

    if not config.DOCUMENTS_DIR.exists():
        print(f"❌ Documents directory not found: {config.DOCUMENTS_DIR}")
        return

    loader = DocumentLoader()
    validator = IngestionValidator()
    documents = loader.load_directory(config.DOCUMENTS_DIR)

    if not documents:
        print("❌ No documents found")
        return

    print(f"Found {len(documents)} documents\n")

    valid_count = 0
    results = []

    for doc in documents:
        filename = doc['metadata']['filename']
        is_valid, reason, missing = validator.validate_document(doc)
        domain_score = validator.get_domain_score(doc.get("content", ""))
        category = validator.suggest_document_category(doc.get("content", ""))
        results.append({
            'file': filename,
            'valid': is_valid,
            'reason': reason,
            'missing': missing,
            'score': domain_score,
            'category': category,
            'size': len(doc.get("content", ""))
        })
        if is_valid:
            valid_count += 1

    print("✅ Valid Documents:")
    for r in results:
        if r['valid']:
            print(f"  • {r['file']:<40} Score: {r['score']:.2f}  Category: {r['category']}")

    invalid_count = len(results) - valid_count
    if invalid_count > 0:
        print("\n❌ Invalid Documents:")
        for r in results:
            if not r['valid']:
                print(f"  • {r['file']:<40} Reason: {r['reason']}")
                if r['missing']:
                    print(f"       Missing: {', '.join(r['missing'])}")

    print("\n" + "=" * 70)
    print(f"Total: {len(documents)} documents")
    print(f"Valid: {valid_count} ({valid_count/len(documents)*100:.1f}%)")
    print(f"Invalid: {invalid_count} ({invalid_count/len(documents)*100:.1f}%)")

if __name__ == "__main__":
    main()