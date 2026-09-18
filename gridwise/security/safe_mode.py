"""Automated Safe Fallback Mode Manager.

Orchestrates fail-closed operations and system quarantine when threats or provider
failures occur, guaranteeing that unverified external inputs cannot compromise the
grid dispatch optimizer.
"""

import threading
from typing import Dict, Any, Optional
from gridwise.security.audit import audit_logger


class SafeModeManager:
    """Manages the application's safe mode lifecycle."""

    def __init__(self):
        self._is_active = False
        self._reason: Optional[str] = None
        self._activated_at: Optional[str] = None
        self._lock = threading.Lock()

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._is_active

    @property
    def reason(self) -> Optional[str]:
        with self._lock:
            return self._reason

    def activate_safe_mode(self, reason: str, request_id: Optional[str] = None) -> None:
        """Activates safe fallback mode and records an audit event."""
        with self._lock:
            self._is_active = True
            self._reason = reason
            
        audit_logger.log_security_event(
            severity="CRITICAL",
            component="safe_mode_manager",
            reason=reason,
            action="safe_mode_activated",
            request_id=request_id
        )

    def deactivate_safe_mode(self, request_id: Optional[str] = None) -> None:
        """Deactivates safe mode after manual operator remediation."""
        with self._lock:
            self._is_active = False
            self._reason = None

        audit_logger.log_security_event(
            severity="INFO",
            component="safe_mode_manager",
            reason="manual_operator_reset",
            action="safe_mode_deactivated",
            request_id=request_id
        )

    def get_status(self) -> Dict[str, Any]:
        """Returns safe mode diagnostic status."""
        with self._lock:
            return {
                "safe_mode_active": self._is_active,
                "activation_reason": self._reason
            }


# Global safe mode singleton
safe_mode_manager = SafeModeManager()
