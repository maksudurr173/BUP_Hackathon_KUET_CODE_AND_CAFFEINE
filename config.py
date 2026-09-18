"""Configuration module for GridWise application.

Loads environment variables using Pydantic Settings and validates
all operational, security, optimization, and LLM parameters.
"""

from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application Environment
    ENVIRONMENT: str = Field(default="development", description="Current environment (development, production, testing)")
    HOST: str = Field(default="0.0.0.0", description="Host to bind server")
    PORT: int = Field(default=8000, description="Port to bind server")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # Security & CORS
    CORS_ALLOWED_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
        description="Comma-separated list of allowed origins"
    )
    ALLOWED_HOSTS: str = Field(default="*", description="Allowed host headers")
    MAX_REQUEST_BODY_BYTES: int = Field(default=1_048_576, description="Maximum payload size in bytes (1MB)")
    MAX_NOTE_LENGTH: int = Field(default=500, description="Maximum character length per operator note")

    # Authentication
    AUTH_ENABLED: bool = Field(default=False, description="Whether authentication is required for optimization endpoints")
    API_KEY_SECRET: str = Field(default="dev_secret_api_key_gridwise_12345", description="Shared API key for service-to-service auth")
    JWT_SECRET_KEY: str = Field(default="dev_jwt_secret_key_gridwise_67890", description="JWT secret key for token signature")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT signing algorithm")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, description="Access token expiration in minutes")

    # LLM Settings
    LLM_PROVIDER: str = Field(default="mock", description="LLM provider: mock, openai, gemini, anthropic, or custom")
    LLM_API_KEY: Optional[str] = Field(default=None, description="API key for the LLM provider")
    LLM_MODEL_NAME: str = Field(default="gpt-4o-mini", description="Model name to invoke")
    LLM_BASE_URL: Optional[str] = Field(default=None, description="Custom base URL for LLM API calls")
    LLM_TIMEOUT_SECONDS: float = Field(default=10.0, description="Timeout for external LLM API calls in seconds")

    # LLM Circuit Breaker
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = Field(default=3, description="Consecutive failures before opening circuit")
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS: float = Field(default=30.0, description="Seconds to wait before trying half-open")
    CIRCUIT_BREAKER_HALF_OPEN_LIMIT: int = Field(default=2, description="Successful calls in half-open state before closing")

    # Rate Limiting & Incident Detection
    RATE_LIMIT_ENABLED: bool = Field(default=True, description="Enable sliding-window rate limiting")
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(default=60, description="Max requests allowed per client IP per minute")
    RATE_LIMIT_BURST_CAPACITY: int = Field(default=10, description="Burst bucket size above per-minute allowance")
    SECURITY_ALERT_THRESHOLD_VIOLATIONS: int = Field(default=5, description="Violations count that triggers a security alert")

    # Mathematical Solver Settings
    SOLVER_TIMEOUT_SECONDS: float = Field(default=10.0, description="Timeout for optimization solver in seconds")
    SOLVER_TOLERANCE: float = Field(default=0.01, description="Physical and financial verification tolerance in kWh/BDT")

    @property
    def cors_origins_list(self) -> List[str]:
        if self.CORS_ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]


# Global settings singleton
settings = Settings()
