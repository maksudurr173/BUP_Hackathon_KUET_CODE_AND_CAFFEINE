"""Deterministic mathematical solver using HiGHS algorithm.

Executes linear program optimization, extracts hourly dispatch decisions,
computes top-level energy metrics, and handles solver timeouts safely.
"""

import time
import logging
from typing import List, Tuple
import numpy as np
from scipy.optimize import linprog

from config import settings
from gridwise.app.models import BatteryConfig, HourlyPlanEntry, BatteryActionType
from gridwise.directives.engine import ProcessedDirectives
from gridwise.optimization.model import EnergyOptimizationModelBuilder, OptimizationProblem
from gridwise.app.errors import OptimizationFailedException, OptimizationTimeoutException

logger = logging.getLogger("gridwise.solver")


class EnergyOptimizer:
    """Solves the 24-hour campus energy dispatch problem."""

    @classmethod
    def solve(
        cls,
        demand: List[float],
        solar: List[float],
        tariff: List[float],
        battery: BatteryConfig,
        processed_directives: ProcessedDirectives,
        timeout_seconds: float = 10.0
    ) -> List[HourlyPlanEntry]:
        """Builds and solves the optimization model, returning the 24-hour hourly plan."""
        # 1. Build standard LP formulation
        problem = EnergyOptimizationModelBuilder.build(
            demand=demand,
            tariff=tariff,
            battery=battery,
            processed=processed_directives
        )

        # 2. Execute HiGHS solver
        start_time = time.time()
        try:
            # scipy linprog options for HiGHS
            options = {
                "time_limit": timeout_seconds,
                "presolve": True,
                "disp": False
            }
            
            res = linprog(
                c=problem.c,
                A_eq=problem.A_eq if len(problem.A_eq) > 0 else None,
                b_eq=problem.b_eq if len(problem.b_eq) > 0 else None,
                A_ub=problem.A_ub if len(problem.A_ub) > 0 else None,
                b_ub=problem.b_ub if len(problem.b_ub) > 0 else None,
                bounds=problem.bounds,
                method="highs",
                options=options
            )
        except Exception as exc:
            logger.error(f"Solver threw an unexpected exception: {exc}")
            raise OptimizationFailedException(f"Solver internal failure: {str(exc)}")

        elapsed = time.time() - start_time
        if elapsed > timeout_seconds and not res.success:
            raise OptimizationTimeoutException("Optimization solver exceeded the execution time limit")

        if not res.success:
            logger.warning(f"HiGHS solver failed: status={res.status}, message={res.message}")
            raise OptimizationFailedException(
                f"No feasible energy dispatch schedule found: {res.message}"
            )

        # 3. Extract variable solutions
        x = res.x
        T = 24
        G = x[0:T]
        S = x[T:2*T]
        C = x[2*T:3*T]
        D = x[3*T:4*T]
        E = x[4*T:5*T]

        # Clean tiny numerical noise (e.g. 1e-10)
        G = np.where(G < 1e-6, 0.0, G)
        S = np.where(S < 1e-6, 0.0, S)
        C = np.where(C < 1e-6, 0.0, C)
        D = np.where(D < 1e-6, 0.0, D)

        hourly_plan: List[HourlyPlanEntry] = []
        for h in range(T):
            c_val = float(C[h])
            d_val = float(D[h])
            
            # Determine battery action and rate
            if c_val > 1e-4 and c_val >= d_val:
                action: BatteryActionType = "charging"
                battery_kwh = c_val
            elif d_val > 1e-4:
                action = "discharging"
                battery_kwh = d_val
            else:
                action = "idle"
                battery_kwh = 0.0

            entry = HourlyPlanEntry(
                hour=h,
                grid_kwh=round(float(G[h]), 4),
                solar_used_kwh=round(float(S[h]), 4),
                battery_action=action,
                battery_kwh=round(battery_kwh, 4),
                battery_energy_after_kwh=round(float(E[h]), 4)
            )
            hourly_plan.append(entry)

        return hourly_plan
