"""Security, Rate Limiting, and Request Tracing Middlewares for GridWise."""

import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from config import settings
from gridwise.app.errors import create_error_response
from gridwise.app.security import get_security_headers
from gridwise.security.rate_limiter import rate_limiter
from gridwise.security.threat_detection import threat_detector
from gridwise.security.audit import audit_logger


class SecurityMiddleware(BaseHTTPMiddleware):
    """Unified security middleware handling request-id, rate limits, size limits, and security headers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.time()

        # 1. Correlation ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        client_ip = request.client.host if request.client else "127.0.0.1"
        request.state.client_ip = client_ip

        # 2. Check Client Quarantine (Cyber-Breach Defense)
        is_blocked, remaining_time = threat_detector.is_client_blocked(client_ip)
        if is_blocked:
            return create_error_response(
                code="SECURITY_BLOCKED",
                message=f"Access temporarily quarantined due to security violations. Try again in {int(remaining_time)} seconds.",
                status_code=status.HTTP_403_FORBIDDEN,
                request_id=request_id
            )

        # 3. Payload size check
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length_int = int(content_length)
                if length_int > settings.MAX_REQUEST_BODY_BYTES:
                    threat_detector.record_violation(client_ip, "oversized_payload", request_id)
                    return create_error_response(
                        code="INVALID_REQUEST",
                        message=f"Request payload size ({length_int} bytes) exceeds maximum allowable limit of {settings.MAX_REQUEST_BODY_BYTES} bytes",
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        request_id=request_id
                    )
            except ValueError:
                pass

        # 4. Rate Limiting (Skip /health endpoint to prevent monitoring false positives)
        if settings.RATE_LIMIT_ENABLED and request.url.path not in ("/health", "/"):
            allowed, remaining, retry_after = rate_limiter.is_allowed(client_ip)
            if not allowed:
                threat_detector.record_violation(client_ip, "rate_limit_exceeded", request_id)
                resp = create_error_response(
                    code="RATE_LIMITED",
                    message="Too many requests. Please slow down and respect rate limits.",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    request_id=request_id
                )
                resp.headers["Retry-After"] = str(int(retry_after) + 1)
                return resp

        # 5. Process Request
        response: Response = await call_next(request)

        # 6. Inject Security and Tracing Headers
        security_headers = get_security_headers()
        for k, v in security_headers.items():
            response.headers[k] = v

        process_time = round((time.time() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = str(process_time)

        return response
