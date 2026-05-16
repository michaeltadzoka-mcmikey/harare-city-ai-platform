import json
import re
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from app.config import config
from app.core.normalizer import TextNormalizer

class DocumentLoader:
    def __init__(self):
        self.normalizer = TextNormalizer()

    def load_file(self, file_path: Path) -> Dict[str, Any]:
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        metadata = {
            "source": str(file_path),
            "filename": file_path.name,
            "extension": file_path.suffix,
            "directory": str(file_path.parent)
        }

        if file_path.suffix == '.json':
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            content = self.normalizer.normalize_json_content(data)
            return {"content": content, "metadata": metadata, "size": len(content)}

        with open(file_path, 'r', encoding='utf-8-sig') as f:
            raw_text = f.read()

        top_metadata = {}
        lines = raw_text.split('\n')
        content_lines = []
        in_metadata_block = False
        metadata_block_lines = []

        top_pattern = re.compile(r'^#\s*([^:]+):\s*(.*)$')

        for line in lines:
            line = line.rstrip('\r')
            if not in_metadata_block and line.startswith('# ') and ':' in line:
                match = top_pattern.match(line)
                if match:
                    key = match.group(1).strip().lower()
                    value = match.group(2).strip()
                    top_metadata[key] = value
            elif line.strip() == '## METADATA_BLOCK':
                in_metadata_block = True
            elif in_metadata_block and line.strip() == '## CONTENT_BLOCK':
                in_metadata_block = False
            elif in_metadata_block:
                metadata_block_lines.append(line)
            else:
                content_lines.append(line)

        # Parse metadata block
        block_metadata = {}
        for line in metadata_block_lines:
            line = line.strip()
            if not line or ':' not in line:
                continue
            key, val = line.split(':', 1)
            key = key.strip().lower()
            val = val.strip()
            if val.startswith('[') and val.endswith(']'):
                items = [v.strip().strip('"').strip("'") for v in val[1:-1].split(',') if v.strip()]
                block_metadata[key] = items
            else:
                block_metadata[key] = val

        # Convert known list fields even if they appear as comma-separated strings
        list_fields = ["locations", "topic_tags", "related_documents", "prerequisites"]
        for field in list_fields:
            if field in block_metadata and isinstance(block_metadata[field], str):
                # split by comma and strip
                block_metadata[field] = [x.strip() for x in block_metadata[field].split(',') if x.strip()]

        # Convert cross_service_flag to boolean
        if "cross_service_flag" in block_metadata:
            val = block_metadata["cross_service_flag"]
            if isinstance(val, str):
                block_metadata["cross_service_flag"] = val.lower() in ("true", "yes", "1")
            elif isinstance(val, bool):
                block_metadata["cross_service_flag"] = val

        # Merge (top-level overrides block)
        merged = {**block_metadata, **top_metadata}
        metadata.update(merged)

        content = '\n'.join(content_lines).strip()
        content = self.normalizer.normalize(content)

        return {
            "content": content,
            "metadata": metadata,
            "size": len(content)
        }

    def load_directory(self, directory: Path) -> List[Dict[str, Any]]:
        documents = []
        for ext in config.SUPPORTED_EXTENSIONS:
            for file_path in directory.rglob(f"*{ext}"):
                if file_path.is_file():
                    try:
                        doc = self.load_file(file_path)
                        documents.append(doc)
                    except Exception as e:
                        print(f"Warning: Could not load {file_path}: {e}")
        return documents