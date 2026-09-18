"""Automated Cyber-Breach and Threat Detection System.

Analyzes request patterns in real time to detect anomalous activity, prompt injection
campaigns, repeated schema tampering, and brute-force access attempts.
"""

import time
import threading
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from config import settings
from gridwise.security.audit import audit_logger


class ThreatDetector:
    """Tracks security violations and detects cyber threats."""

    def __init__(self, alert_threshold: int = 5, window_seconds: float = 300.0):
        self.alert_threshold = alert_threshold
        self.window_seconds = window_seconds
        
        # client_ip -> list of (timestamp, violation_type)
        self._violations: Dict[str, List[Tuple[float, str]]] = defaultdict(list)
        self._blocked_clients: Dict[str, float] = {}  # client_ip -> unblock_timestamp
        self._lock = threading.Lock()

    def record_violation(
        self,
        client_ip: str,
        violation_type: str,
        request_id: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> bool:
        """Records a violation and checks if the threat threshold is breached.
        
        Returns:
            True if client is now temporarily blocked/flagged as threat, False otherwise.
        """
        now = time.time()
        with self._lock:
            # Clean old violations outside the time window
            cutoff = now - self.window_seconds
            self._violations[client_ip] = [
                (t, v) for (t, v) in self._violations[client_ip] if t >= cutoff
            ]
            self._violations[client_ip].append((now, violation_type))

            violation_count = len(self._violations[client_ip])

            if violation_count >= self.alert_threshold:
                # Temporarily block client for 5 minutes
                unblock_time = now + 300.0
                self._blocked_clients[client_ip] = unblock_time

                audit_logger.log_security_event(
                    severity="CRITICAL",
                    component="threat_detection",
                    reason="threshold_exceeded_automated_block",
                    action="temporary_ip_quarantine",
                    request_id=request_id,
                    details={
                        "client_ip": client_ip,
                        "violation_count": violation_count,
                        "latest_violation": violation_type,
                        "quarantine_seconds": 300,
                        "extra": details or {}
                    }
                )
                return True
            else:
                audit_logger.log_security_event(
                    severity="WARNING",
                    component="threat_detection",
                    reason="security_violation_recorded",
                    action="increment_threat_score",
                    request_id=request_id,
                    details={
                        "client_ip": client_ip,
                        "violation_type": violation_type,
                        "violation_count": violation_count,
                        "threshold": self.alert_threshold
                    }
                )
                return False

    def is_client_blocked(self, client_ip: str) -> Tuple[bool, float]:
        """Checks if a client is currently in security quarantine.
        
        Returns:
            (is_blocked, remaining_quarantine_seconds)
        """
        now = time.time()
        with self._lock:
            if client_ip in self._blocked_clients:
                unblock_time = self._blocked_clients[client_ip]
                if now < unblock_time:
                    return True, round(unblock_time - now, 1)
                else:
                    # Quarantine expired
                    del self._blocked_clients[client_ip]
            return False, 0.0

    def unblock_client(self, client_ip: str) -> None:
        """Manually unblocks a client from quarantine."""
        with self._lock:
            if client_ip in self._blocked_clients:
                del self._blocked_clients[client_ip]
            if client_ip in self._violations:
                del self._violations[client_ip]


# Global threat detector instance
threat_detector = ThreatDetector(
    alert_threshold=settings.SECURITY_ALERT_THRESHOLD_VIOLATIONS
)
