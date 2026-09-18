"""Web application security configurations and header policies."""

from typing import Dict
from config import settings


def get_security_headers() -> Dict[str, str]:
    """Returns production-grade HTTP security headers."""
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none';",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }
    if settings.ENVIRONMENT == "production":
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    return headers
