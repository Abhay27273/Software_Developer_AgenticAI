"""
QA Agent Configuration
Manages Fast QA and Deep QA mode settings.
"""

import os
from dataclasses import dataclass
from typing import Literal

QAMode = Literal["fast", "deep"]

@dataclass
class QAConfig:
    """Configuration for QA Agent modes."""
    
    # Mode selection
    mode: QAMode = "fast"
    
    # Timeouts
    fast_timeout: int = 60
    deep_timeout: int = 90
    test_execution_timeout: int = 15
    fix_attempt_timeout: int = 15
    retest_timeout: int = 5
    
    # Confidence thresholds
    confidence_pass: float = 0.8      # ≥0.8 → Deploy
    confidence_flag: float = 0.5      # ≥0.5 → Flag + Deploy
    confidence_fail: float = 0.5      # <0.5 → Send to Dev
    
    # Code limits for LLM review
    max_code_chars_per_file: int = 3000
    total_code_limit: int = 15000
    
    # Test generation
    max_test_lines: int = 50
    test_truncate_chars: int = 1500
    test_output_limit: int = 500
    
    @classmethod
    def from_env(cls) -> "QAConfig":
        """Load configuration from environment variables."""
        return cls(
            mode=os.getenv("QA_MODE", "fast").lower(),
            fast_timeout=int(os.getenv("FAST_QA_TIMEOUT", "60")),
            deep_timeout=int(os.getenv("DEEP_QA_TIMEOUT", "90")),
            confidence_pass=float(os.getenv("QA_CONFIDENCE_PASS", "0.8")),
            confidence_flag=float(os.getenv("QA_CONFIDENCE_FLAG", "0.5")),
            max_code_chars_per_file=int(os.getenv("QA_MAX_CODE_CHARS", "3000")),
            total_code_limit=int(os.getenv("QA_TOTAL_CODE_LIMIT", "15000")),
        )
    
    def get_status(self, confidence: float) -> Literal["passed", "flagged", "failed"]:
        """Determine QA status based on confidence score."""
        if confidence >= self.confidence_pass:
            return "passed"
        elif confidence >= self.confidence_flag:
            return "flagged"
        else:
            return "failed"
