"""Incident Response Coordinator.

Provides unified incident handling, alerting hooks, and remediation actions.
"""

from typing import Any, Dict, Optional
from gridwise.security.audit import audit_logger
from gridwise.security.threat_detection import threat_detector
from gridwise.security.safe_mode import safe_mode_manager
from gridwise.llm.circuit_breaker import llm_circuit_breaker


class IncidentResponseCoordinator:
    """Coordinates automated incident mitigation and alerting."""

    @classmethod
    def handle_security_incident(
        cls,
        severity: str,
        incident_type: str,
        client_ip: str,
        request_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Handles security incidents with appropriate automated responses."""
        # 1. Log incident
        audit_logger.log_security_event(
            severity=severity,
            component="incident_response",
            reason=incident_type,
            action="automated_mitigation",
            request_id=request_id,
            details={"client_ip": client_ip, **(details or {})}
        )

        # 2. Record violation against client
        is_blocked = threat_detector.record_violation(
            client_ip=client_ip,
            violation_type=incident_type,
            request_id=request_id,
            details=details
        )

        # 3. If critical or repeated attacks on LLM integration, trip circuit breaker
        if severity == "CRITICAL" and "llm" in incident_type:
            llm_circuit_breaker.trip_manually()
            safe_mode_manager.activate_safe_mode(
                reason=f"Compromise detected in LLM pipeline: {incident_type}",
                request_id=request_id
            )
