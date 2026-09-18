"""FastAPI Web Application and Route Definitions for GridWise."""

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List
from fastapi import FastAPI, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import settings
from gridwise.app.models import (
    OptimizeEnergyRequest,
    OptimizeEnergyResponse,
    DirectiveInterpretation,
)
from gridwise.app.errors import (
    GridWiseException,
    gridwise_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    SafeModeActiveException,
)
from gridwise.app.middleware import SecurityMiddleware
from gridwise.auth.dependencies import get_current_user, require_role, AuthenticatedUser
from gridwise.auth.authorization import Role
from gridwise.directives.engine import DirectiveEngine
from gridwise.llm.interpreter import llm_interpreter
from gridwise.llm.circuit_breaker import llm_circuit_breaker
from gridwise.optimization.solver import EnergyOptimizer
from gridwise.validation.schedule_validator import ScheduleValidator
from gridwise.security.safe_mode import safe_mode_manager
from gridwise.security.audit import audit_logger

logger = logging.getLogger("gridwise.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("GridWise Energy Optimization Backend starting up...")
    yield
    logger.info("GridWise Energy Optimization Backend shutting down cleanly...")


def create_app() -> FastAPI:
    """Factory function to build and configure the FastAPI application."""
    app = FastAPI(
        title="GridWise Energy Optimization API",
        description="Production-grade, LLM-assisted campus energy scheduling & security backend",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    )

    # 1. CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # 2. Security Middleware (Request size, rate limiting, request ID, security headers)
    app.add_middleware(SecurityMiddleware)

    # 3. Exception Handlers
    app.add_exception_handler(GridWiseException, gridwise_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ==========================================================================
    # Public & Health Endpoints
    # ==========================================================================

    @app.get("/health", tags=["Health"], status_code=status.HTTP_200_OK)
    async def health():
        """Lightweight, public health check endpoint."""
        return {"status": "ok"}

    # ==========================================================================
    # Main Optimization Endpoint
    # ==========================================================================

    @app.post(
        "/optimize-energy",
        response_model=OptimizeEnergyResponse,
        tags=["Optimization"],
        status_code=status.HTTP_200_OK,
        summary="Optimize 24-hour campus energy schedule"
    )
    async def optimize_energy(
        request: Request,
        payload: OptimizeEnergyRequest,
        user: AuthenticatedUser = Depends(get_current_user)
    ) -> OptimizeEnergyResponse:
        """Main GridWise pipeline:
        
        1. Validate request payload & battery parameters.
        2. Verify Safe Mode status (fail-closed if active).
        3. Interpret operator notes via LLM with guardrails & circuit breaker.
        4. Apply validated directives to physical constraints.
        5. Solve mathematical LP optimization using HiGHS.
        6. Independently replay & validate candidate schedule against physics.
        7. Compute final summary totals directly from hourly plan.
        8. Return verified response matching GridWise specification.
        """
        request_id = getattr(request.state, "request_id", "req_unknown")

        # 1. Fail-closed check if safe mode is actively quarantining the system
        if safe_mode_manager.is_active:
            raise SafeModeActiveException(
                f"System is in Safe Mode ({safe_mode_manager.reason}). Free-form operator notes cannot be processed."
            )

        # 2. LLM Interpretation & Guardrails
        directives: List[DirectiveInterpretation] = await llm_interpreter.interpret_notes(
            notes=payload.operator_notes,
            battery_capacity_kwh=payload.battery.capacity_kwh,
            request_id=request_id
        )

        # 3. Directive Application & Constraint Compilation
        processed = DirectiveEngine.apply_directives(
            base_solar=payload.solar,
            battery_config=payload.battery,
            directives=directives
        )

        # 4. Mathematical Optimization via HiGHS
        hourly_plan = EnergyOptimizer.solve(
            demand=payload.demand,
            solar=payload.solar,
            tariff=payload.tariff,
            battery=payload.battery,
            processed_directives=processed,
            timeout_seconds=settings.SOLVER_TIMEOUT_SECONDS
        )

        # 5. Independent Physical Verification & Total Metrics Calculation
        total_grid, total_cost, peak_grid = ScheduleValidator.validate_and_compute_metrics(
            demand=payload.demand,
            tariff=payload.tariff,
            battery=payload.battery,
            processed_directives=processed,
            hourly_plan=hourly_plan,
            tolerance=settings.SOLVER_TOLERANCE
        )

        # 6. Concise Human-Readable Plan Summary
        plan_summary = ScheduleValidator.generate_plan_summary(
            scenario_id=payload.scenario_id,
            directives=directives,
            hourly_plan=hourly_plan,
            total_grid_kwh=total_grid,
            total_cost_bdt=total_cost,
            peak_grid_kwh=peak_grid,
            applied_directives_summary=processed.applied_directives_summary
        )

        return OptimizeEnergyResponse(
            scenario_id=payload.scenario_id,
            directive_interpretation=directives,
            hourly_plan=hourly_plan,
            total_grid_kwh=total_grid,
            total_cost_bdt=total_cost,
            peak_grid_kwh=peak_grid,
            plan_summary=plan_summary
        )

    # ==========================================================================
    # Diagnostic / Administrative Endpoints (Protected)
    # ==========================================================================

    @app.get(
        "/security/events",
        tags=["Security"],
        dependencies=[Depends(require_role({Role.ADMIN}))]
    )
    async def get_security_events(limit: int = 50):
        """Returns recent sanitized security audit events (Admin only)."""
        return {"events": audit_logger.get_recent_events(limit=min(limit, 100))}

    @app.get(
        "/system/status",
        tags=["System"],
        dependencies=[Depends(require_role({Role.ADMIN, Role.OPERATOR}))]
    )
    async def get_system_status():
        """Returns internal circuit breaker and safe mode diagnostic status."""
        return {
            "circuit_breaker": llm_circuit_breaker.get_status(),
            "safe_mode": safe_mode_manager.get_status()
        }

    # ==========================================================================
    # Frontend Static Files
    # ==========================================================================
    import os
    frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
    if os.path.exists(frontend_dir):
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

    return app



# Root ASGI application
app = create_app()

