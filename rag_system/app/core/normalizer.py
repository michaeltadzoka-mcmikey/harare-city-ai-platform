import re
from typing import Optional

class TextNormalizer:
    @staticmethod
    def normalize(text: str) -> str:
        """Normalize text for consistent processing."""
        if not text:
            return ""
        
        # Replace various newlines with single \n
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove multiple consecutive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Strip whitespace from each line while preserving structure
        lines = []
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped:  # Skip empty lines
                lines.append(stripped)
        
        # Join with single newline
        return '\n'.join(lines)
    
    @staticmethod
    def normalize_json_content(data: dict) -> str:
        """Convert JSON to readable text."""
        lines = []
        for key, value in data.items():
            if isinstance(value, (int, float)):
                lines.append(f"{key}: {value}")
            elif isinstance(value, str):
                lines.append(f"{key}: {value}")
            elif isinstance(value, list):
                lines.append(f"{key}: " + ", ".join(str(v) for v in value))
        return '\n'.join(lines)