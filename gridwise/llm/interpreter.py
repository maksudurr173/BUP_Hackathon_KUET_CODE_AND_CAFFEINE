"""LLM Operator-Note Interpreter.

Interprets natural-language operator notes into structured, mathematically verifiable
directives using an LLM or deterministic rule-based NLP parser, guarded by
threat detection, strict JSON parsing, schema validation, and circuit breakers.
"""

import re
import json
import logging
import httpx
from typing import Any, Dict, List, Optional, Tuple

from config import settings
from gridwise.app.models import DirectiveInterpretation
from gridwise.app.errors import (
    LLMUnavailableException,
    LLMInvalidResponseException,
    SecurityBlockedException,
    SafeModeActiveException,
)
from gridwise.llm.prompt import SYSTEM_PROMPT, build_user_prompt
from gridwise.llm.guardrails import LLMGuardrails
from gridwise.llm.circuit_breaker import llm_circuit_breaker
from gridwise.security.audit import audit_logger

logger = logging.getLogger("gridwise.llm")


class LLMInterpreter:
    """Interprets operator notes into validated directives."""

    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        self.api_key = settings.LLM_API_KEY
        self.model_name = settings.LLM_MODEL_NAME
        self.base_url = settings.LLM_BASE_URL
        self.timeout = settings.LLM_TIMEOUT_SECONDS

    async def interpret_notes(
        self,
        notes: List[str],
        battery_capacity_kwh: Optional[float] = None,
        request_id: Optional[str] = None
    ) -> List[DirectiveInterpretation]:
        """Main entrypoint to interpret a list of operator notes.
        
        Args:
            notes: 1-3 operator notes
            battery_capacity_kwh: Optional capacity for boundary validation
            request_id: Optional request correlation ID
            
        Returns:
            List of DirectiveInterpretation objects, one per note.
        """
        # Step 1: Pre-scan for malicious prompt injection attempts
        for idx, note in enumerate(notes):
            is_suspicious, reason = LLMGuardrails.scan_for_prompt_injection(note)
            if is_suspicious:
                audit_logger.log_security_event(
                    severity="HIGH",
                    component="llm_interpreter",
                    reason="prompt_injection_attempt",
                    action="blocked_request",
                    request_id=request_id,
                    details={"note_index": idx, "reason": reason}
                )
                raise SecurityBlockedException(
                    f"Malicious or adversarial prompt pattern detected in operator note {idx}"
                )

        # Step 2: Check circuit breaker
        if not llm_circuit_breaker.can_execute():
            audit_logger.log_security_event(
                severity="WARNING",
                component="llm_circuit_breaker",
                reason="circuit_breaker_open",
                action="fallback_rejection",
                request_id=request_id
            )
            raise LLMUnavailableException("LLM service is currently unavailable (circuit breaker is OPEN)")

        # Step 3: Call Provider
        try:
            if self.provider == "mock":
                raw_response = self._interpret_with_mock(notes)
            elif self.provider in ("openai", "custom"):
                raw_response = await self._call_openai_compatible_api(notes)
            elif self.provider == "gemini":
                raw_response = await self._call_gemini_api(notes)
            elif self.provider == "anthropic":
                raw_response = await self._call_anthropic_api(notes)
            else:
                raw_response = self._interpret_with_mock(notes)

            # Step 4: Extract JSON & Validate Schema
            parsed_json = LLMGuardrails.extract_and_parse_json(raw_response)
            validated_directives = LLMGuardrails.validate_llm_directives(
                parsed_json=parsed_json,
                expected_note_count=len(notes),
                battery_capacity_kwh=battery_capacity_kwh
            )

            # Record success with circuit breaker
            llm_circuit_breaker.record_success()
            return validated_directives

        except (SecurityBlockedException, SafeModeActiveException):
            raise
        except LLMInvalidResponseException as exc:
            llm_circuit_breaker.record_failure(exc)
            audit_logger.log_security_event(
                severity="WARNING",
                component="llm_guardrails",
                reason="invalid_model_response",
                action="record_failure",
                request_id=request_id,
                details={"error": str(exc)}
            )
            raise
        except Exception as exc:
            llm_circuit_breaker.record_failure(exc)
            audit_logger.log_security_event(
                severity="HIGH",
                component="llm_provider",
                reason="provider_call_exception",
                action="trip_counter_incremented",
                request_id=request_id,
                details={"error_type": type(exc).__name__}
            )
            raise LLMUnavailableException(f"Failed to communicate with LLM provider: {str(exc)}")

    # --------------------------------------------------------------------------
    # Mock / Deterministic NLP Parser (Production fallback & standalone engine)
    # --------------------------------------------------------------------------
    def _interpret_with_mock(self, notes: List[str]) -> str:
        """High-precision NLP rule parser capable of interpreting complex paraphrases."""
        directives = []

        for idx, note in enumerate(notes):
            parsed_directive = self._parse_single_note_nlp(idx, note)
            directives.append(parsed_directive)

        return json.dumps({"directives": directives})

    def _parse_single_note_nlp(self, note_idx: int, note: str) -> Dict[str, Any]:
        """Parses a single operator note using natural language semantics."""
        text = note.lower()

        # Parse hours
        hours = self._extract_time_window(text)

        # 1. Solar reduction checks
        # Examples: "PV production will drop to 20%", "80% reduction in solar", "solar reduced by 50%"
        if any(kw in text for kw in ["solar", "pv", "rooftop solar", "photovoltaic", "sun"]):
            # Check for factor/percentage
            factor = self._extract_solar_factor(text)
            if factor is not None and hours:
                return {
                    "note_index": note_idx,
                    "applies": True,
                    "directive_type": "solar_reduction",
                    "structured_adjustment": {
                        "hours": hours,
                        "factor": factor
                    }
                }

        # 2. Minimum battery reserve checks
        # Examples: "Keep at least 120 kWh in the battery", "minimum 80 kWh reserve", "hold battery at 100kwh"
        if any(kw in text for kw in ["reserve", "keep at least", "minimum energy", "hold at least", "maintain at least", "minimum battery"]):
            energy_val = self._extract_kwh_value(text)
            if energy_val is not None and hours:
                return {
                    "note_index": note_idx,
                    "applies": True,
                    "directive_type": "minimum_battery_reserve",
                    "structured_adjustment": {
                        "hours": hours,
                        "minimum_energy_kwh": energy_val
                    }
                }

        # 3. No charge window checks
        # Examples: "Do not charge", "no charging", "pause battery charging", "avoid charging"
        is_no_charge = ("charge" in text or "charging" in text) and any(
            kw in text for kw in ["no charge", "no charging", "do not charge", "avoid charg", "halt charge", "disable charge", "stop charg", "pause charg"]
        )
        if is_no_charge and "discharge" not in text:
            if hours:
                return {
                    "note_index": note_idx,
                    "applies": True,
                    "directive_type": "no_charge_window",
                    "structured_adjustment": {
                        "hours": hours
                    }
                }

        # 4. No discharge window checks
        # Examples: "Do not discharge", "no discharging", "avoid battery discharge", "halt discharge", "avoid discharging battery"
        is_no_discharge = ("discharge" in text or "discharging" in text) and any(
            kw in text for kw in ["no discharge", "no discharging", "do not discharge", "avoid", "halt", "disable", "stop", "pause", "prevent"]
        )
        if is_no_discharge:
            if hours:
                return {
                    "note_index": note_idx,
                    "applies": True,
                    "directive_type": "no_discharge_window",
                    "structured_adjustment": {
                        "hours": hours
                    }
                }


        # 5. Max grid window checks
        # Examples: "Limit grid import to 50 kWh", "max grid 40 kWh", "grid cap of 60 kwh"
        if any(kw in text for kw in ["grid", "grid import", "import limit", "grid cap"]):
            if any(kw in text for kw in ["limit", "max", "cap", "not exceed", "restrict"]):
                grid_val = self._extract_kwh_value(text)
                if grid_val is not None and hours:
                    return {
                        "note_index": note_idx,
                        "applies": True,
                        "directive_type": "max_grid_window",
                        "structured_adjustment": {
                            "hours": hours,
                            "max_grid_kwh": grid_val
                        }
                    }

        # Default fallback to no_op
        return {
            "note_index": note_idx,
            "applies": False,
            "directive_type": "no_op",
            "structured_adjustment": None
        }

    def _extract_time_window(self, text: str) -> List[int]:
        """Extracts normalized start-inclusive, end-exclusive hours from natural text."""
        # Pattern with optional AM/PM on start and end:
        # e.g., "6 pm and 8 pm", "1:00 pm to 3:00 pm", "11:00 and 13:00", "18:00 to 22:00"
        pattern = re.search(
            r"(?:between|from|during|in)?\s*(\d{1,2})(?::00)?\s*(am|pm)?\s*(?:to|and|-)\s*(\d{1,2})(?::00)?\s*(am|pm)?",
            text,
            re.IGNORECASE
        )
        if pattern:
            start_val = int(pattern.group(1))
            start_ampm = (pattern.group(2) or "").lower()
            end_val = int(pattern.group(3))
            end_ampm = (pattern.group(4) or "").lower()

            # Inherit am/pm if only end specified (e.g. "1 to 3 pm")
            if not start_ampm and end_ampm:
                if end_ampm == "pm" and start_val < 12 and start_val <= end_val:
                    start_ampm = "pm"
                elif end_ampm == "am" and start_val < 12 and start_val <= end_val:
                    start_ampm = "am"

            # Apply PM conversion
            if start_ampm == "pm" and start_val < 12:
                start_val += 12
            elif start_ampm == "am" and start_val == 12:
                start_val = 0

            if end_ampm == "pm" and end_val < 12:
                end_val += 12
            elif end_ampm == "am" and end_val == 12:
                end_val = 0

            if 0 <= start_val < end_val <= 24:
                return list(range(start_val, end_val))

        # Check single hour e.g. "at 14:00" or "hour 14" or "at 2 pm"
        single_h = re.search(r"(?:at|hour)\s*(\d{1,2})(?::00)?\s*(am|pm)?", text, re.IGNORECASE)
        if single_h:
            h = int(single_h.group(1))
            ampm = (single_h.group(2) or "").lower()
            if ampm == "pm" and h < 12:
                h += 12
            elif ampm == "am" and h == 12:
                h = 0
            if 0 <= h <= 23:
                return [h]

        return []

    def _extract_solar_factor(self, text: str) -> Optional[float]:
        """Extracts remaining solar factor from percentages in text."""
        # Case 1: "drop to X%", "drops to X%", "falls to X%", "reduced to X%" -> factor = X/100
        drop_to_match = re.search(r"(?:drop|drops|fall|falls|reduced|down|to|about)\s*to\s*(\d{1,3})%", text)
        if drop_to_match:
            pct = float(drop_to_match.group(1))
            return max(0.0, min(1.0, round(pct / 100.0, 4)))

        # Case 2: "reduced by X%", "X% reduction", "X% solar reduction", "X% drop", "cut by X%" -> factor = 1.0 - (X/100)
        reduced_by_match = re.search(r"(?:reduced\s*by|cut\s*by|drop\s*of)\s*(\d{1,3})%", text)
        if reduced_by_match:
            pct = float(reduced_by_match.group(1))
            return max(0.0, min(1.0, round((100.0 - pct) / 100.0, 4)))

        pct_reduction_match = re.search(r"(\d{1,3})%\s*(?:(?:rooftop\s+)?solar\s+|pv\s+)?(?:reduction|cut|drop|decrease|outage|dip)", text)
        if pct_reduction_match:
            pct = float(pct_reduction_match.group(1))
            return max(0.0, min(1.0, round((100.0 - pct) / 100.0, 4)))

        # Case 3: "X% solar availability" -> factor = X/100
        avail_match = re.search(r"(\d{1,3})%\s*(?:capacity|availability|generation|production|output)", text)
        if avail_match:
            pct = float(avail_match.group(1))
            return max(0.0, min(1.0, round(pct / 100.0, 4)))

        return None

    def _extract_kwh_value(self, text: str) -> Optional[float]:
        """Extracts numeric kWh values from text."""
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:kwh|kw|units)", text)
        if match:
            return float(match.group(1))
        
        # Fallback to standalone number
        num_match = re.search(r"(?:least|minimum|limit|max|to)\s*(\d+(?:\.\d+)?)", text)
        if num_match:
            return float(num_match.group(1))
        return None


    # --------------------------------------------------------------------------
    # External API Integrations (OpenAI / Gemini / Anthropic)
    # --------------------------------------------------------------------------
    async def _call_openai_compatible_api(self, notes: List[str]) -> str:
        url = self.base_url or "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(notes)}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _call_gemini_api(self, notes: List[str]) -> str:
        url = self.base_url or f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key} if self.api_key else {}
        prompt_text = f"{SYSTEM_PROMPT}\n\n{build_user_prompt(notes)}"
        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

    async def _call_anthropic_api(self, notes: List[str]) -> str:
        url = self.base_url or "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": build_user_prompt(notes)}
            ],
            "temperature": 0.0
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]


# Global interpreter instance
llm_interpreter = LLMInterpreter()
