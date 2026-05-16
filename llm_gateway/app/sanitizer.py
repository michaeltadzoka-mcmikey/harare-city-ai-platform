# llm_gateway/app/sanitizer.py
"""
Sanitizer for Harare Chatbot Gateway v5.3
Defends against prompt injection in retrieved content
"""

import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class Sanitizer:
    """
    Prompt injection defense system.
    
    Strips potential control instructions from retrieved text BEFORE
    it reaches the LLM or template engine.
    """
    
    # Patterns that look like prompt injections
    INJECTION_PATTERNS = [
        r"ignore (previous|all|above) instructions?",
        r"disregard (previous|all|above) instructions?",
        r"forget (previous|all|above) instructions?",
        r"new instructions?:",
        r"system:",
        r"assistant:",
        r"you are now",
        r"act as",
        r"pretend (you are|to be)",
        r"roleplay",
        r"\[SYSTEM\]",
        r"\[INST\]",
        r"<\|system\|>",
        r"<\|user\|>",
        r"<\|assistant\|>",
        # Common attack vectors
        r"```\s*system",
        r"```\s*prompt",
    ]
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.log_stripped = self.config.get("log_stripped_content", True)
        
        # Compile patterns
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.INJECTION_PATTERNS
        ]
        
        # Load custom blocklist if provided
        blocklist_path = self.config.get("blocklist_path")
        if blocklist_path:
            self._load_blocklist(blocklist_path)
        
        logger.info(f"Sanitizer initialized (enabled: {self.enabled})")
    
    def sanitize_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize a single document.
        
        Args:
            document: Document from RAG
            
        Returns:
            Sanitized document
        """
        if not self.enabled:
            return document
        
        original_text = document.get("text", "")
        
        if not original_text:
            return document
        
        # Clean the text
        cleaned_text, violations = self._clean_text(original_text)
        
        if violations:
            logger.warning(
                f"Sanitizer removed {len(violations)} potential injections "
                f"from document {document.get('id', 'unknown')}"
            )
            
            if self.log_stripped:
                for violation in violations[:3]:  # Log first 3
                    logger.info(f"Stripped: {violation[:100]}")
            
            document["text"] = cleaned_text
            document["sanitizer_violations"] = len(violations)
            document["sanitizer_applied"] = True
        
        return document
    
    def sanitize_text(self, text: str) -> str:
        """
        Sanitize plain text.
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text
        """
        if not self.enabled:
            return text
        
        cleaned_text, _ = self._clean_text(text)
        return cleaned_text
    
    def _clean_text(self, text: str) -> tuple[str, List[str]]:
        """
        Clean text and return violations.
        
        Args:
            text: Original text
            
        Returns:
            Tuple of (cleaned_text, violations_found)
        """
        violations = []
        cleaned = text
        
        # Check each pattern
        for pattern in self.compiled_patterns:
            matches = pattern.finditer(cleaned)
            for match in matches:
                violation_text = match.group(0)
                violations.append(violation_text)
                
                # Replace with sanitized version
                cleaned = cleaned.replace(
                    violation_text,
                    "[CONTENT REMOVED FOR SAFETY]"
                )
        
        # Additional cleaning: remove excessive control characters
        cleaned = self._remove_control_chars(cleaned)
        
        # Remove markdown code blocks that look suspicious
        cleaned = self._sanitize_code_blocks(cleaned)
        
        return cleaned, violations
    
    def _remove_control_chars(self, text: str) -> str:
        """Remove control characters that could break parsing."""
        # Keep only printable ASCII + common unicode
        cleaned = ''.join(
            char for char in text
            if char.isprintable() or char in ['\n', '\r', '\t']
        )
        return cleaned
    
    def _sanitize_code_blocks(self, text: str) -> str:
        """
        Sanitize markdown code blocks that might contain prompts.
        
        Keep code blocks but remove suspicious content.
        """
        # Pattern for markdown code blocks
        code_block_pattern = r'```(\w*)\n(.*?)\n```'
        
        def check_block(match):
            language = match.group(1)
            content = match.group(2)
            
            # Check if content looks like a prompt injection
            suspicious = any(
                pattern.search(content)
                for pattern in self.compiled_patterns
            )
            
            if suspicious:
                logger.debug(f"Sanitizing suspicious code block (lang: {language})")
                return f"```{language}\n[CODE BLOCK REMOVED FOR SAFETY]\n```"
            
            return match.group(0)
        
        cleaned = re.sub(
            code_block_pattern,
            check_block,
            text,
            flags=re.DOTALL | re.IGNORECASE
        )
        
        return cleaned
    
    def _load_blocklist(self, path: str):
        """Load custom blocklist from file."""
        try:
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        pattern = re.compile(line, re.IGNORECASE)
                        self.compiled_patterns.append(pattern)
            
            logger.info(f"Loaded custom blocklist from {path}")
        except FileNotFoundError:
            logger.warning(f"Blocklist file not found: {path}")
        except Exception as e:
            logger.error(f"Error loading blocklist: {e}")
    
    def check_user_input(self, user_message: str) -> tuple[bool, Optional[str]]:
        """
        Check if user input contains injection attempts.
        
        This is a DIFFERENT use case than document sanitization.
        For user input, we detect but DON'T strip (just warn).
        
        Args:
            user_message: User's message
            
        Returns:
            Tuple of (is_safe, warning_message)
        """
        for pattern in self.compiled_patterns:
            if pattern.search(user_message):
                logger.warning(
                    f"Potential prompt injection in user input: "
                    f"{user_message[:100]}"
                )
                return False, (
                    "Your message contains content that could be misinterpreted. "
                    "Please rephrase your question."
                )
        
        return True, None


# Global instance
sanitizer = Sanitizer()