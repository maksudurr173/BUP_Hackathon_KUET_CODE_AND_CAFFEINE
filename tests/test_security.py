"""Tests for security, threat detection, rate limiting, and auth."""

import pytest
from gridwise.security.rate_limiter import TokenBucketRateLimiter
from gridwise.security.threat_detection import ThreatDetector
from gridwise.security.audit import sanitize_value, AuditLogger
from gridwise.security.safe_mode import SafeModeManager
from gridwise.auth.authentication import create_access_token, verify_jwt_token, verify_api_key
from gridwise.auth.authorization import Role, verify_role_authorized
from gridwise.app.errors import ForbiddenException, UnauthorizedException


def test_token_bucket_rate_limiter():
    limiter = TokenBucketRateLimiter(requests_per_minute=2, burst_capacity=0)
    # Allowed 2 requests
    allowed1, _, _ = limiter.is_allowed("192.168.1.100")
    allowed2, _, _ = limiter.is_allowed("192.168.1.100")
    assert allowed1 is True
    assert allowed2 is True

    # 3rd request should be blocked
    allowed3, remaining, retry_after = limiter.is_allowed("192.168.1.100")
    assert allowed3 is False
    assert retry_after > 0


def test_threat_detector_quarantine():
    detector = ThreatDetector(alert_threshold=3, window_seconds=10.0)
    ip = "10.0.0.99"
    assert not detector.is_client_blocked(ip)[0]

    # Record 2 violations -> not blocked
    detector.record_violation(ip, "bad_input")
    detector.record_violation(ip, "bad_input")
    assert not detector.is_client_blocked(ip)[0]

    # 3rd violation triggers quarantine
    is_blocked = detector.record_violation(ip, "prompt_injection")
    assert is_blocked is True
    assert detector.is_client_blocked(ip)[0] is True


def test_audit_logger_sanitizes_secrets():
    payload = {
        "api_key": "secret_key_12345",
        "nested": {
            "password": "super_secret_password",
            "safe_field": "public_data"
        }
    }
    sanitized = sanitize_value(payload)
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["password"] == "[REDACTED]"
    assert sanitized["nested"]["safe_field"] == "public_data"


def test_jwt_auth_and_roles():
    token = create_access_token(subject="user123", role="operator")
    decoded = verify_jwt_token(token)
    assert decoded["sub"] == "user123"
    assert decoded["role"] == "operator"

    # Operator can perform operator role
    verify_role_authorized("operator", {Role.OPERATOR})

    # Operator cannot perform admin-only role
    with pytest.raises(ForbiddenException):
        verify_role_authorized("operator", {Role.ADMIN})

    # Admin can perform operator and admin roles
    verify_role_authorized("admin", {Role.OPERATOR})
    verify_role_authorized("admin", {Role.ADMIN})


def test_safe_mode_manager():
    sm = SafeModeManager()
    assert sm.is_active is False
    sm.activate_safe_mode("Circuit tripped due to security alert")
    assert sm.is_active is True
    sm.deactivate_safe_mode()
    assert sm.is_active is False
