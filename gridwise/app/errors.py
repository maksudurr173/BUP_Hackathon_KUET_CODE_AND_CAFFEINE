"""Error handling and custom exception hierarchy for GridWise.

Ensures that errors are consistently formatted, securely masked,
and mapped to appropriate HTTP status codes without leaking internal secrets.
"""

from typing import Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class GridWiseException(Exception):
    """Base exception for all GridWise application errors."""
    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class InvalidRequestException(GridWiseException):
    def __init__(self, message: str):
        super().__init__(message, code="INVALID_REQUEST", status_code=status.HTTP_400_BAD_REQUEST)


class UnauthorizedException(GridWiseException):
    def __init__(self, message: str = "Authentication credentials were not provided or are invalid"):
        super().__init__(message, code="UNAUTHORIZED", status_code=status.HTTP_401_UNAUTHORIZED)


class ForbiddenException(GridWiseException):
    def __init__(self, message: str = "Insufficient permissions to perform this operation"):
        super().__init__(message, code="FORBIDDEN", status_code=status.HTTP_403_FORBIDDEN)


class RateLimitedException(GridWiseException):
    def __init__(self, message: str = "Rate limit exceeded. Please slow down your requests."):
        super().__init__(message, code="RATE_LIMITED", status_code=status.HTTP_429_TOO_MANY_REQUESTS)


class LLMUnavailableException(GridWiseException):
    def __init__(self, message: str = "LLM interpretation service is currently unavailable"):
        super().__init__(message, code="LLM_UNAVAILABLE", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


class LLMInvalidResponseException(GridWiseException):
    def __init__(self, message: str = "LLM generated an unparseable or invalid directive"):
        super().__init__(message, code="LLM_INVALID_RESPONSE", status_code=422)


class SecurityBlockedException(GridWiseException):
    def __init__(self, message: str = "Request blocked due to security or threat policy violation"):
        super().__init__(message, code="SECURITY_BLOCKED", status_code=status.HTTP_403_FORBIDDEN)


class SafeModeActiveException(GridWiseException):
    def __init__(self, message: str = "System is in safe mode; unverified natural language instructions cannot be processed"):
        super().__init__(message, code="SAFE_MODE_ACTIVE", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


class OptimizationFailedException(GridWiseException):
    def __init__(self, message: str = "Mathematical optimization solver could not find a feasible schedule"):
        super().__init__(message, code="OPTIMIZATION_FAILED", status_code=422)



class OptimizationTimeoutException(GridWiseException):
    def __init__(self, message: str = "Mathematical solver exceeded computational time limit"):
        super().__init__(message, code="OPTIMIZATION_TIMEOUT", status_code=status.HTTP_504_GATEWAY_TIMEOUT)


class ValidationFailedException(GridWiseException):
    def __init__(self, message: str = "Independent schedule validation failed to verify candidate solution"):
        super().__init__(message, code="VALIDATION_FAILED", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


def create_error_response(code: str, message: str, status_code: int, request_id: Optional[str] = None) -> JSONResponse:
    """Helper to build standard uniform error JSON response."""
    payload = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if request_id:
        payload["error"]["request_id"] = request_id
    return JSONResponse(status_code=status_code, content=payload)


async def gridwise_exception_handler(request: Request, exc: GridWiseException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return create_error_response(
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        request_id=request_id
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    # Extract clean, user-friendly error messages without raw pydantic internals
    error_messages = []
    for err in exc.errors():
        loc = " -> ".join([str(l) for l in err.get("loc", []) if l != "body"])
        msg = err.get("msg", "Validation error")
        if loc:
            error_messages.append(f"{loc}: {msg}")
        else:
            error_messages.append(msg)
    
    combined_message = "; ".join(error_messages) if error_messages else "Request validation failed."
    return create_error_response(
        code="INVALID_REQUEST",
        message=combined_message,
        status_code=status.HTTP_400_BAD_REQUEST,
        request_id=request_id
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    code = "INTERNAL_ERROR"
    if exc.status_code == status.HTTP_404_NOT_FOUND:
        code = "NOT_FOUND"
    elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
        code = "UNAUTHORIZED"
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        code = "FORBIDDEN"
    elif exc.status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
        code = "METHOD_NOT_ALLOWED"

    return create_error_response(
        code=code,
        message=str(exc.detail),
        status_code=exc.status_code,
        request_id=request_id
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    # Never leak internal exception traces to the client
    return create_error_response(
        code="INTERNAL_ERROR",
        message="An unexpected internal error occurred. Please contact system support.",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        request_id=request_id
    )
