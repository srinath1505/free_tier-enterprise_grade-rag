import re
from typing import Tuple, List, Optional
from backend.core.config import settings

class SecurityException(Exception):
    pass

class Guardrail:
    def check(self, text: str) -> Tuple[bool, str]:
        """
        Returns (is_safe, reason)
        """
        raise NotImplementedError

class InputValidator(Guardrail):
    def __init__(self, max_length: int = 2000):
        self.max_length = max_length

    def check(self, text: str) -> Tuple[bool, str]:
        if len(text) > self.max_length:
            return False, f"Input exceeds maximum length of {self.max_length} characters."
        if not text.strip():
            return False, "Input is empty."
        return True, "OK"

class PromptInjectionGuard(Guardrail):
    def __init__(self):
        # Heuristics for common jailbreak attempts
        # \s* allows for "D A N", "ignore   previous"
        self.patterns = [
            re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
            re.compile(r"you\s+are\s+now", re.IGNORECASE),
            re.compile(r"system\s+prompt", re.IGNORECASE),
            re.compile(r"simulat(?:e|ing)", re.IGNORECASE),
            re.compile(r"jailbreak", re.IGNORECASE),
            re.compile(r"D[\.\s]*A[\.\s]*N", re.IGNORECASE), # Matches DAN, D.A.N, D A N
        ]

    def check(self, text: str) -> Tuple[bool, str]:
        for pattern in self.patterns:
            if pattern.search(text):
                return False, f"Potential Prompt Injection detected: pattern '{pattern.pattern}'"
        return True, "OK"

class ToxicityGuard(Guardrail):
    def __init__(self):
        # 1. Fail-safe Keyword Blocklist
        # Enhanced to catch some leetspeak via normalization later
        self.blocklist = [
            "bomb", "kill", "suicide", "murder", "terrorist", "poison", 
            "hack", "exploit", "malware", "virus"
        ]
        
        # Leetspeak Map
        self.leet_map = str.maketrans("013457!@", "oieastia")
        
        # 2. Model placeholder
        self.use_model_check = False 

    def normalize(self, text: str) -> str:
        """
        Simple normalization: lower case, remove special chars/spaces, handle leetspeak
        """
        # 1. Lowercase
        text = text.lower()
        # 2. Simple Leetspeak Decode
        text = text.translate(self.leet_map)
        return text

    def check(self, text: str) -> Tuple[bool, str]:
        normalized = self.normalize(text)
        
        # Layer 1: Keywords found in normalized text
        # Checks "b0mb" -> "bomb"
        for word in self.blocklist:
            if word in normalized: 
                 return False, f"Toxic content detected (keyword: {word})"
                 
        return True, "OK"

class SecurityLayer:
    def __init__(self):
        self.validator = InputValidator()
        self.injection_guard = PromptInjectionGuard()
        self.toxicity_guard = ToxicityGuard()
        
    def validate(self, text: str) -> str:
        """
        Runs all guardrails. Raises SecurityException if unsafe.
        Returns the safe text (potentially identical).
        """
        # 1. Basic Validation
        safe, reason = self.validator.check(text)
        if not safe:
            raise SecurityException(f"Validation Error: {reason}")
            
        # 2. Prompt Injection
        safe, reason = self.injection_guard.check(text)
        if not safe:
            raise SecurityException(f"Security Alert: {reason}")
            
        # 3. Toxicity
        safe, reason = self.toxicity_guard.check(text)
        if not safe:
            raise SecurityException(f"Safety Violation: {reason}")
            
        return text
