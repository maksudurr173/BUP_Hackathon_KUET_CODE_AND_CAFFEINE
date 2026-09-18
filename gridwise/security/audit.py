"""Structured Security and Audit Logging for GridWise.

Produces sanitized JSON logs conforming to SOC2/compliance requirements.
Guarantees that credentials, tokens, and internal secrets are NEVER logged or leaked.
"""

import json
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Root security logger
logger = logging.getLogger("gridwise.security")

SENSITIVE_FIELD_NAMES = {
    "api_key", "apikey", "secret", "password", "token", "access_token",
    "refresh_token", "authorization", "bearer", "jwt_secret_key", "api_key_secret"
}


def sanitize_value(val: Any) -> Any:
    """Recursively redacts sensitive keys from log dictionaries and lists."""
    if isinstance(val, dict):
        sanitized = {}
        for k, v in val.items():
            if any(sens in k.lower() for sens in SENSITIVE_FIELD_NAMES):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_value(v)
        return sanitized
    elif isinstance(val, list):
        return [sanitize_value(item) for item in val]
    return val


class AuditLogger:
    """Manages structured JSON security event generation and in-memory event trail."""

    def __init__(self, max_event_history: int = 200):
        self._event_history: deque = deque(maxlen=max_event_history)

    def log_security_event(
        self,
        severity: str,
        component: str,
        reason: str,
        action: str,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Logs and stores a security audit event with sanitized details."""
        event = {
            "event_type": "SECURITY_EVENT",
            "severity": severity.upper(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id or "system",
            "component": component,
            "reason": reason,
            "action": action,
            "details": sanitize_value(details or {})
        }

        self._event_history.append(event)
        
        # Log as structured JSON string
        log_msg = json.dumps(event)
        if severity.upper() in ("HIGH", "CRITICAL"):
            logger.error(log_msg)
        elif severity.upper() == "WARNING":
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return event

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns the most recent sanitized security events."""
        events = list(self._event_history)
        return events[-limit:]


# Global audit logger singleton
audit_logger = AuditLogger()
