"""Mathematical formulation of the 24-hour energy optimization model.

Constructs standard linear programming (LP/MILP) vectors and matrices:
c (objective), A_eq / b_eq (equality constraints), A_ub / b_ub (inequality constraints),
and variable bounds.
"""

from dataclasses import dataclass
from typing import List, Tuple
import numpy as np

from gridwise.app.models import BatteryConfig
from gridwise.directives.engine import ProcessedDirectives


@dataclass
class OptimizationProblem:
    """Standard form representation of LP: min c^T x s.t. A_ub x <= b_ub, A_eq x == b_eq, bounds."""
    c: np.ndarray
    A_eq: np.ndarray
    b_eq: np.ndarray
    A_ub: np.ndarray
    b_ub: np.ndarray
    bounds: List[Tuple[float, float]]
    num_hours: int = 24

    # Variable index offsets (each spans 24 hours):
    # x[0..23]   = G[h] (Grid Import)
    # x[24..47]  = S[h] (Solar Used)
    # x[48..71]  = C[h] (Battery Charge)
    # x[72..95]  = D[h] (Battery Discharge)
    # x[96..119] = E[h] (Battery State of Charge after hour h)


class EnergyOptimizationModelBuilder:
    """Builds LP formulation for the 24-hour campus energy scheduling problem."""

    TOTAL_VARS = 24 * 5  # 120 variables

    @classmethod
    def build(
        cls,
        demand: List[float],
        tariff: List[float],
        battery: BatteryConfig,
        processed: ProcessedDirectives
    ) -> OptimizationProblem:
        """Constructs full linear program matrices from inputs and active directives."""
        T = 24
        
        # Variable index helpers
        idx_G = lambda h: h
        idx_S = lambda h: T + h
        idx_C = lambda h: 2 * T + h
        idx_D = lambda h: 3 * T + h
        idx_E = lambda h: 4 * T + h

        # 1. Objective: Minimize Sum(G[h] * Tariff[h]) + small tie-breaking penalty
        # Small penalty on C[h] and D[h] (1e-6) prevents simultaneous charging/discharging in degenerate cases
        c = np.zeros(cls.TOTAL_VARS, dtype=float)
        for h in range(T):
            c[idx_G(h)] = tariff[h]
            c[idx_C(h)] = 1e-6
            c[idx_D(h)] = 1e-6

        # 2. Variable Bounds
        bounds: List[Tuple[float, float]] = [(0.0, None)] * cls.TOTAL_VARS

        for h in range(T):
            # Grid import bounds
            max_g = processed.max_grid_limits.get(h, None)
            bounds[idx_G(h)] = (0.0, max_g)

            # Solar used bounds: [0, effective_solar[h]]
            bounds[idx_S(h)] = (0.0, max(0.0, processed.effective_solar[h]))

            # Charge bounds: [0, max_charge], or 0 if in no_charge_hours
            if h in processed.no_charge_hours:
                bounds[idx_C(h)] = (0.0, 0.0)
            else:
                bounds[idx_C(h)] = (0.0, battery.max_charge_kwh)

            # Discharge bounds: [0, max_discharge], or 0 if in no_discharge_hours
            if h in processed.no_discharge_hours:
                bounds[idx_D(h)] = (0.0, 0.0)
            else:
                bounds[idx_D(h)] = (0.0, battery.max_discharge_kwh)

            # Battery energy state bounds: [min_energy[h], capacity]
            min_e = processed.min_battery_energy[h]
            bounds[idx_E(h)] = (min_e, battery.capacity_kwh)

        # 3. Equality Constraints (A_eq x == b_eq)
        # - 24 Energy balance equations: G[h] + S[h] + D[h] - C[h] == Demand[h]
        # - 24 Battery state transitions: E[h] - E[h-1] - C[h] + D[h] == 0  (with E[-1] = initial_energy)
        # - 1 End-of-day neutrality: E[23] == initial_energy
        eq_rows = []
        b_eq = []

        # Energy Balance
        for h in range(T):
            row = np.zeros(cls.TOTAL_VARS, dtype=float)
            row[idx_G(h)] = 1.0
            row[idx_S(h)] = 1.0
            row[idx_D(h)] = 1.0
            row[idx_C(h)] = -1.0
            eq_rows.append(row)
            b_eq.append(demand[h])

        # Battery Transitions
        for h in range(T):
            row = np.zeros(cls.TOTAL_VARS, dtype=float)
            row[idx_E(h)] = 1.0
            row[idx_C(h)] = -1.0
            row[idx_D(h)] = 1.0
            if h == 0:
                eq_rows.append(row)
                b_eq.append(battery.initial_energy_kwh)
            else:
                row[idx_E(h - 1)] = -1.0
                eq_rows.append(row)
                b_eq.append(0.0)

        # End-of-day neutrality: E[23] == initial_energy
        row_eod = np.zeros(cls.TOTAL_VARS, dtype=float)
        row_eod[idx_E(23)] = 1.0
        eq_rows.append(row_eod)
        b_eq.append(battery.initial_energy_kwh)

        A_eq = np.array(eq_rows, dtype=float)
        b_eq_arr = np.array(b_eq, dtype=float)

        # 4. Inequality Constraints (A_ub x <= b_ub)
        # We can leave empty since bounds cover all other constraints cleanly
        A_ub = np.zeros((0, cls.TOTAL_VARS), dtype=float)
        b_ub = np.zeros(0, dtype=float)

        return OptimizationProblem(
            c=c,
            A_eq=A_eq,
            b_eq=b_eq_arr,
            A_ub=A_ub,
            b_ub=b_ub,
            bounds=bounds,
            num_hours=T
        )
