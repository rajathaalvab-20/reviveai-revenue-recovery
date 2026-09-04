# ReviveAI — Safe Automated Revenue Recovery

ReviveAI is a simulation-based AI revenue recovery system that evaluates failed payment events and recommends safe recovery actions. It combines risk assessment, failure diagnosis, deterministic policy guardrails, simulated action execution, and verification into a single recovery pipeline.

The project is designed to demonstrate reliable, explainable, and safety-first payment recovery without connecting to a real payment gateway or moving real money.

## Features

* Risk assessment using a recovery probability.
* Failure diagnosis based on failure type and failure code.
* Deterministic policy decisions with configurable safety guardrails.
* Simulated recovery actions such as retrying a payment, requesting a payment-method update, or escalating for review.
* Verification stage that distinguishes recovered, not recovered, pending, and not-executed outcomes.
* Audit logging for recovery decisions and pipeline stages.
* REST API built with FastAPI.
* Interactive dashboard for submitting payment events and viewing recovery decisions.
* Docker-based execution.
* Automated testing covering validation, policy logic, recovery actions, and edge cases.

## Architecture

```text
Payment Event
      |
      v
Risk Detector
      |
      v
Diagnosis Engine
      |
      v
Policy Engine
      |
      +---- Rejected / Blocked ----> Action Not Executed
      |
      v
Action Engine
      |
      v
Verification Engine
      |
      v
Recovery Outcome
```

## Recovery pipeline

1. **Risk Detector** estimates the probability that a failed payment can be recovered.
2. **Diagnosis Engine** identifies the failure category and recommended recovery strategy.
3. **Policy Engine** applies deterministic safety guardrails before any action is allowed.
4. **Action Engine** executes a simulated recovery action only when the policy approves it.
5. **Verification Engine** evaluates the outcome and records whether the payment was recovered.

## Safety guardrails

ReviveAI follows a fail-closed approach. Recovery actions are not executed when policy validation fails.

The policy engine includes guardrails for:

* Supported failure codes.
* Minimum recovery probability.
* Maximum retry attempts.
* Maximum automatic recovery amount.
* Action consistency.
* Hard-failure protection.
* Input validation and safe transaction identifiers.

The project operates in **simulation mode**. It does not connect to a real payment gateway, initiate real refunds, or transfer real money.

## Tech stack

* **Backend:** Python 3.11.9, FastAPI
* **Frontend:** HTML, CSS, JavaScript
* **API server:** Uvicorn
* **Containerization:** Docker
* **Testing:** Pytest
* **Data format:** JSON

## Project structure

```text
ReviveAI/
├── src/
│   ├── api/
│   │   └── main.py
│   ├── risk/
│   ├── diagnosis/
│   ├── policy/
│   ├── action/
│   ├── verification/
│   └── simulation/
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── tests/
├── results/
│   └── simulation/
├── Dockerfile
├── requirements.txt
└── README.md
```

## Getting started

### Prerequisites

* Docker Desktop
* Git

### 1. Clone the repository

```bash
git clone https://github.com/rajathaalvab-20/reviveai-revenue-recovery.git
cd reviveai-revenue-recovery
```

### 2. Build the Docker image

```bash
docker build -t reviveai .
```

### 3. Run the application

```bash
docker run -p 8000:8000 reviveai
```

### 4. Open the application

```text
http://127.0.0.1:8000
```

### API documentation

```text
http://127.0.0.1:8000/docs
```

### Health check

```text
GET /health
```

### Recovery endpoint

```text
POST /api/v1/recover
```

## API example

### Request

```json
{
  "transaction_id": "API_TEST_002",
  "amount": 5000,
  "payment_method": "CARD",
  "customer_type": "RETURNING",
  "failure_type": "TRANSIENT",
  "failure_code": "BANK_TIMEOUT",
  "attempt_count": 1,
  "previous_transactions": 25,
  "previous_success_rate": 0.92
}
```

### Example response

```json
{
  "transaction_id": "API_TEST_002",
  "recovery_probability": 0.85,
  "risk_level": "LOW",
  "diagnosis": {
    "category": "TRANSIENT",
    "strategy": "RETRY_PAYMENT",
    "retryable": true,
    "automatic_recovery": true
  },
  "policy": {
    "decision": "APPROVED"
  },
  "action": {
    "name": "RETRY_PAYMENT",
    "executed": true
  },
  "verification": {
    "status": "RECOVERED"
  }
}
```

*The response above is illustrative. Actual results depend on the submitted payment event and the recovery pipeline.*

## Simulation results

A batch simulation of **100 payment transactions** was executed to evaluate the recovery pipeline.

| Metric                    |      Result |
| ------------------------- | ----------: |
| Total transactions        |         100 |
| Recovered transactions    |          36 |
| Blocked transactions      |          26 |
| Not recovered             |          38 |
| Failed executions         |           0 |
| Revenue at risk           | ₹383,848.15 |
| Revenue recovered         | ₹168,208.58 |
| Revenue not recovered     | ₹215,639.57 |
| Transaction recovery rate |      36.00% |
| Revenue recovery rate     |      43.82% |

The simulation demonstrates that policy approval and action execution are separate from actual recovery verification.

## Failure recovery and development validation

During development, the application initially exposed a frontend integration issue when the FastAPI server was started directly. The backend returned `200 OK` for the main page, but requests for `style.css` and `app.js` returned `404 Not Found`.

The issue was traced to the frontend being served separately from the backend. The frontend files existed in the `frontend/` directory, and the dashboard loaded correctly when served using Python's local HTTP server.

The development process was:

1. Start the FastAPI backend.
2. Observe the `200 OK` response for the main page.
3. Identify the `404 Not Found` responses for the frontend assets.
4. Verify that the CSS and JavaScript files existed.
5. Serve the frontend separately using a local HTTP server.
6. Confirm that the dashboard rendered correctly.
7. Verify that the API documentation was available at `/docs`.

This issue demonstrated the importance of validating the complete application workflow rather than checking only whether the backend starts successfully.

The project also uses automated testing to validate recovery logic, policy guardrails, action execution, verification outcomes, and edge cases. The test suite currently reports **429 passing tests**.

The batch simulation further validates the distinction between policy approval, action execution, and actual recovery. In the 100-transaction simulation, 36 transactions were recovered, 26 were blocked, and 38 were not recovered. This demonstrates that an approved or executed action does not automatically imply successful revenue recovery.

## Testing

Run the complete test suite:

```bash
pytest -q
```

The project currently has **429 passing tests**.

The tests cover:

* Input validation.
* Risk and diagnosis logic.
* Policy guardrails.
* Action execution.
* Verification outcomes.
* Pipeline integration.
* Edge cases and failure handling.
### Alternative startup method

If Docker is unavailable or the Docker setup does not work, the application can also be run directly using Python.

**Prerequisites:**

* Python 3.11.9
* Git

**1. Create and activate a virtual environment**

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**2. Install dependencies**

```powershell
pip install -r requirements.txt
```

**3. Start the FastAPI backend**

```powershell
python -m src.api.main
```

The API will be available at:

```text
http://127.0.0.1:8000
```

**4. Start the frontend**

Open a second terminal:

```powershell
cd frontend
python -m http.server 5500
```

Open the dashboard:

```text
http://localhost:5500/
```

**5. Open the API documentation**

```text
http://127.0.0.1:8000/docs
```

This alternative method allows the backend and frontend to be run locally without Docker.


## Limitations

* The system uses simulated payment actions rather than a real payment gateway.
* Recovery probabilities are model outputs and are not guaranteed outcomes.
* Verification is based on simulated results or supplied ground-truth outcomes.
* The current simulation enforces a maximum retry-attempt limit but does not implement a configurable cooldown or exponential backoff between retries.
* The current implementation does not perform real financial transactions.
* Production deployment would require additional authentication, monitoring, gateway integration, and operational controls.

## Future improvements

* Integrate with a real payment gateway in a controlled environment.
* Add authentication and role-based access control.
* Add persistent database storage for transactions and audit logs.
* Introduce monitoring and alerting.
* Improve recovery models using historical payment data.
* Add explainable AI visualizations for risk predictions.
* Support configurable recovery policies.
* Add retry scheduling, cooldowns, and exponential backoff.
* Add production-grade observability and deployment automation.

## Conclusion

ReviveAI demonstrates how AI-assisted recovery decisions can be combined with deterministic policy guardrails and verification to create a safer revenue recovery workflow. The project focuses on reliable implementation, transparent decisions, and measurable simulated outcomes rather than uncontrolled automated payment actions.

## License

This project is intended for educational and demonstration purposes.
