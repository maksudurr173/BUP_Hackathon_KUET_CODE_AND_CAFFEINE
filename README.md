# GridWise — Production-Grade Energy Optimization & Security Web Backend

> **LLM-Assisted Campus Energy Scheduling Engine with Multi-Layer Cyber Defense, Mathematical Optimization, and Independent Physics Validation.**

---

## ⚡ Overview

**GridWise** is a production-ready, deterministic, and secure web application backend designed for campus-scale energy dispatch optimization. It interprets natural language operator instructions using an LLM pipeline guarded by prompt-injection scanners, applies structured constraints mathematically, calculates the cost-optimal 24-hour dispatch schedule via the **HiGHS Linear Programming (LP)** solver, independently verifies physical and financial feasibility with a deterministic replay engine, and enforces fail-closed cyber-breach protections.

---

## 🏛️ System Architecture

```text
               HTTP Request (Web Frontend)
                          ↓
               [ Security Middleware ]
               ├─ Request Size Limiter (1MB)
               ├─ Correlation ID Injection (X-Request-ID)
               ├─ Quarantine Defense (Blocked Clients Check)
               ├─ Token-Bucket Rate Limiter (60 req/min)
               └─ Security Headers (CSP, HSTS, X-Frame-Options)
                          ↓
               [ Authentication & RBAC ]
               ├─ JWT Bearer Token / X-API-Key Verification
               └─ Role Authorization (Operator, Admin, ReadOnly)
                          ↓
               [ Request Validation ]
               └─ Strict Pydantic v2 Models (24h bounds, battery physics)
                          ↓
               [ LLM Interpreter & Guardrails ]
               ├─ Threat & Prompt-Injection Scanner
               ├─ Circuit Breaker (CLOSED / OPEN / HALF_OPEN)
               ├─ JSON Extraction & Schema Sanitizer
               └─ Start-Inclusive, End-Exclusive Time Normalization
                          ↓
               [ Directive Processing Engine ]
               └─ Effective Solar, Battery Reserves, Windows, Grid Caps
                          ↓
               [ HiGHS Mathematical LP Solver ]
               └─ Cost Minimization: Min Σ(G[h] * Tariff[h]) + Neutrality
                          ↓
               [ Independent Schedule Replay Validator ]
               ├─ Hourly Energy Balance Conservation: G + S + D = L + C
               ├─ Battery Dynamic Transitions & Bounds
               ├─ End-of-Day Battery Neutrality: E[23] == E_initial
               └─ Top-Level Financial & Physical Metric Recomputation
                          ↓
               [ Verified JSON Response Builder ]
```

---

## 🛡️ Key Security & Resilience Features

| Feature | Description |
|---|---|
| **Prompt Injection Defense** | Regex-based pattern matching and semantic guardrails detect and block adversarial injection attempts. |
| **LLM Circuit Breaker** | Automatically trips from `CLOSED` to `OPEN` after repeated provider failures or timeouts, isolating the LLM. |
| **Automated Safe Fallback** | Safe mode prevents untrusted natural-language inputs from bypassing guardrails when external systems degrade. |
| **Cyber-Breach Defense** | Automated threat detector quarantines abusive client IPs after exceeding configurable security violation thresholds. |
| **Token-Bucket Rate Limiting** | Per-client sliding-window rate limiter with burst capacity protection. |
| **Fail-Closed Principle** | If any input, directive, optimizer solution, or physical constraint fails validation, the system rejects the request rather than guessing. |
| **Zero Secret Leaks** | Structured JSON audit logging redacts API keys, tokens, and credentials automatically. |
| **Enterprise Security Headers** | Injects CSP, X-Frame-Options: DENY, X-Content-Type-Options: nosniff, Referrer-Policy, and HSTS. |

---

## 📋 Supported Directives

GridWise parses operator notes into exactly one of six strictly supported directive types:

1. `solar_reduction`: Modifies solar availability by a multiplier `factor` ($0.0 \le \text{factor} \le 1.0$) for specified hours.
   - Example: *"Expect an 80% reduction in rooftop solar from 1 PM to 3 PM"* $\rightarrow$ `hours: [13, 14]`, `factor: 0.2`.
2. `minimum_battery_reserve`: Enforces $E[h] \ge \text{minimum\_energy\_kwh}$ for specified hours.
   - Example: *"Keep at least 60 kWh in the battery between 18:00 and 21:00"* $\rightarrow$ `hours: [18, 19, 20]`, `minimum_energy_kwh: 60.0`.
3. `no_charge_window`: Enforces battery charging rate $C[h] = 0$ for specified hours.
   - Example: *"Do not charge the battery between 14:00 and 16:00"* $\rightarrow$ `hours: [14, 15]`.
4. `no_discharge_window`: Enforces battery discharging rate $D[h] = 0$ for specified hours.
   - Example: *"Avoid battery discharge between 6 PM and 8 PM"* $\rightarrow$ `hours: [18, 19]`.
5. `max_grid_window`: Enforces grid import limit $G[h] \le \text{max\_grid\_kwh}$ for specified hours.
   - Example: *"Limit grid import to 50 kWh between 18:00 and 20:00"* $\rightarrow$ `hours: [18, 19]`, `max_grid_kwh: 50.0`.
6. `no_op`: Informational, unrelated, or irrelevant notes produce no constraint adjustments (`applies = false`, `structured_adjustment = null`).

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+ (or Docker)
- pip

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/your-org/gridwise-backend.git
cd gridwise-backend

# Create virtual environment
python -m venv venv
# Linux/macOS:
source venv/bin/activate
# Windows:
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Key configuration options:

```env
ENVIRONMENT=development
PORT=8000
AUTH_ENABLED=false
LLM_PROVIDER=mock       # options: mock, openai, gemini, anthropic, custom
LLM_API_KEY=
RATE_LIMIT_ENABLED=true
SOLVER_TIMEOUT_SECONDS=10.0
```

### 3. Running the Server

```bash
uvicorn gridwise.app.api:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation is available at `http://localhost:8000/docs` (in non-production mode).

---

## 📡 API Reference

### 1. Health Check

```http
GET /health
```

#### Response (`200 OK`)
```json
{
  "status": "ok"
}
```

---

### 2. Energy Optimization

```http
POST /optimize-energy
Content-Type: application/json
```

#### Request Payload
```json
{
  "scenario_id": "campus_scenario_01",
  "demand": [
    15, 12, 10, 10, 12, 18, 30, 45, 60, 70, 75, 80,
    85, 80, 75, 70, 65, 80, 95, 90, 70, 50, 35, 20
  ],
  "solar": [
    0, 0, 0, 0, 0, 5, 20, 40, 60, 80, 90, 95,
    90, 85, 70, 50, 25, 10, 0, 0, 0, 0, 0, 0
  ],
  "tariff": [
    5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0,
    10.0, 10.0, 10.0, 10.0, 10.0, 15.0, 15.0, 15.0, 15.0, 10.0, 5.0, 5.0
  ],
  "battery": {
    "capacity_kwh": 100.0,
    "max_charge_kwh": 25.0,
    "max_discharge_kwh": 25.0,
    "initial_energy_kwh": 40.0,
    "min_energy_kwh": 10.0
  },
  "operator_notes": [
    "PV production will drop to about 20% between 13:00 and 15:00.",
    "Keep at least 60 kWh in the battery from 18:00 to 21:00 for campus event."
  ]
}
```

#### Response Payload (`200 OK`)
```json
{
  "scenario_id": "campus_scenario_01",
  "directive_interpretation": [
    {
      "note_index": 0,
      "applies": true,
      "directive_type": "solar_reduction",
      "structured_adjustment": {
        "hours": [13, 14],
        "factor": 0.2
      }
    },
    {
      "note_index": 1,
      "applies": true,
      "directive_type": "minimum_battery_reserve",
      "structured_adjustment": {
        "hours": [18, 19, 20],
        "minimum_energy_kwh": 60.0
      }
    }
  ],
  "hourly_plan": [
    {
      "hour": 0,
      "grid_kwh": 15.0,
      "solar_used_kwh": 0.0,
      "battery_action": "idle",
      "battery_kwh": 0.0,
      "battery_energy_after_kwh": 40.0
    }
    // ... exactly 24 entries (hours 0-23)
  ],
  "total_grid_kwh": 795.0,
  "total_cost_bdt": 7925.0,
  "peak_grid_kwh": 70.0,
  "plan_summary": "Schedule for scenario 'campus_scenario_01' optimized with total grid consumption of 795.00 kWh at an aggregate cost of 7925.00 BDT (peak grid import: 70.00 kWh)..."
}
```

---

### 3. Error Responses

All errors return a predictable, machine-readable JSON structure:

```json
{
  "error": {
    "code": "SECURITY_BLOCKED",
    "message": "Malicious or adversarial prompt pattern detected in operator note 0",
    "request_id": "4168c92b-8a21-4f9e-b9ef-29778736bb87"
  }
}
```

#### Standard Error Categories
- `INVALID_REQUEST` (400)
- `UNAUTHORIZED` (401)
- `FORBIDDEN` / `SECURITY_BLOCKED` (403)
- `RATE_LIMITED` (429)
- `LLM_INVALID_RESPONSE` (422)
- `OPTIMIZATION_FAILED` (422)
- `SAFE_MODE_ACTIVE` (503)
- `LLM_UNAVAILABLE` (503)
- `OPTIMIZATION_TIMEOUT` (504)
- `VALIDATION_FAILED` / `INTERNAL_ERROR` (500)

---

## 🧪 Testing

Run the full automated test suite with pytest:

```bash
pytest -v
```

### Test Coverage Highlights
- **Request Validation**: Schema integrity, 24-value arrays, battery bounds.
- **Directives Engine**: All 6 directive types, multiple directive composition.
- **LLM Guardrails**: Prompt injection detection, circuit breaker transitions, natural language paraphrasing.
- **Mathematical Optimizer**: HiGHS solver optimality, battery neutrality, reserve & window constraints.
- **Independent Replay Validator**: Physical verification, tampering detection.
- **Web Security**: Rate limiter token bucket, IP quarantine, secret redaction, JWT RBAC.
- **Integration Tests**: End-to-end `/health`, `/optimize-energy`, and public benchmark cases.

---

## 🐳 Docker Deployment

Build and run using Docker:

```bash
# Build the image
docker build -t gridwise-backend:latest .

# Run the container
docker run -d -p 8000:8000 --name gridwise gridwise-backend:latest

# Check health
curl http://localhost:8000/health
```

---

## 👥 Team
Built with ❤️ by **CODE AND CAFFEINE** for the BUP Hackathon.
