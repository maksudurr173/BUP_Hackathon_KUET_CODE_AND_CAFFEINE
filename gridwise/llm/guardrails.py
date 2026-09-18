"""LLM Guardrails and Prompt Injection Security Defense.

Inspects incoming operator notes for malicious prompt injection attempts,
sanitizes LLM outputs, enforces strict structured output rules, and prevents
unauthorized behavioral overrides.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from gridwise.app.models import DirectiveInterpretation
from gridwise.directives.validator import validate_all_directives
from gridwise.app.errors import (
    LLMInvalidResponseException,
    SecurityBlockedException,
    InvalidRequestException,
)


# Known prompt injection & security bypass patterns
SUSPICIOUS_PROMPT_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"system\s+prompt",
    r"disregard\s+(all\s+)?rules",
    r"you\s+are\s+now\s+(an?\s+)?admin",
    r"reveal\s+(the\s+)?(api_?key|secret|password|token)",
    r"override\s+(all\s+)?(safety|security|optimization)\s+rules",
    r"exec\s*\(",
    r"eval\s*\(",
    r"__import__",
    r"process\.env",
    r"os\.environ",
    r"/etc/passwd",
    r"curl\s+http",
    r"bypass\s+validation",
    r"<script\b",
    r"drop\s+table",
    r"union\s+select",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_PROMPT_PATTERNS]


class LLMGuardrails:
    """Deterministic security guardrails for LLM input and output validation."""

    @classmethod
    def scan_for_prompt_injection(cls, text: str) -> Tuple[bool, Optional[str]]:
        """Scans input text for known prompt injection and adversarial patterns.
        
        Returns:
            (is_suspicious, matched_pattern_description)
        """
        for pattern in COMPILED_PATTERNS:
            if pattern.search(text):
                return True, f"Suspicious prompt pattern detected: '{pattern.pattern}'"
        return False, None

    @classmethod
    def extract_and_parse_json(cls, raw_text: str) -> Dict[str, Any]:
        """Extracts JSON object from raw LLM output, stripping markdown code fences."""
        cleaned = raw_text.strip()
        # Strip markdown ```json ... ``` or ``` ... ```
        if "```" in cleaned:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
            if match:
                cleaned = match.group(1).strip()

        try:
            parsed = json.loads(cleaned)
            if not isinstance(parsed, dict):
                raise LLMInvalidResponseException("LLM output must be a top-level JSON object")
            return parsed
        except json.JSONDecodeError as exc:
            raise LLMInvalidResponseException(f"Failed to decode LLM response as valid JSON: {str(exc)}")

    @classmethod
    def validate_llm_directives(
        cls,
        parsed_json: Dict[str, Any],
        expected_note_count: int,
        battery_capacity_kwh: Optional[float] = None
    ) -> List[DirectiveInterpretation]:
        """Validates that parsed JSON strictly adheres to the directive schema and note count."""
        directives_raw = parsed_json.get("directives")
        if not isinstance(directives_raw, list):
            raise LLMInvalidResponseException("LLM JSON response must contain a 'directives' array")

        if len(directives_raw) != expected_note_count:
            raise LLMInvalidResponseException(
                f"LLM produced {len(directives_raw)} directives, expected exactly {expected_note_count}"
            )

        candidate_directives: List[DirectiveInterpretation] = []
        for idx, item in enumerate(directives_raw):
            if not isinstance(item, dict):
                raise LLMInvalidResponseException(f"Directive entry {idx} must be a JSON object")

            try:
                candidate = DirectiveInterpretation.model_validate(item)
                candidate_directives.append(candidate)
            except Exception as e:
                raise LLMInvalidResponseException(
                    f"Directive schema validation failed for item {idx}: {str(e)}"
                )

        # Run through strict deterministic validator
        try:
            return validate_all_directives(
                candidate_directives,
                expected_count=expected_note_count,
                battery_capacity_kwh=battery_capacity_kwh
            )
        except InvalidRequestException as exc:
            raise LLMInvalidResponseException(f"Deterministic directive validation failed: {exc.message}")
