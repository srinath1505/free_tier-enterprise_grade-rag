import re
from typing import List

class InputSanitizer:
    def __init__(self):
        # Compiled regex patterns for performance
        self.patterns = {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'phone': re.compile(r'\b(?:\+?(\d{1,3}))?[-. (]*(\d{3})[-. )]*(\d{3})[-. ]*(\d{4})\b'),
            'credit_card': re.compile(r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b'),
            'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
        }

    def sanitize(self, text: str) -> str:
        """
        Redacts PII from the input text.
        """
        sanitized_text = text
        for pii_type, pattern in self.patterns.items():
            sanitized_text = pattern.sub(f"<{pii_type.upper()}_REDACTED>", sanitized_text)
        return sanitized_text

    def contains_pii(self, text: str) -> bool:
        """
        Checks if text contains any PII patterns.
        """
        for pattern in self.patterns.values():
            if pattern.search(text):
                return True
        return False
