from __future__ import annotations

"""
ReviveAI FastAPI API

Compatibility layer around the existing ReviveAI pipeline.

The existing pipeline uses legacy absolute imports such as:

    from risk_detector import detect_risk
    from diagnosis_engine import diagnose_payment
    from policy_engine import evaluate_policy
    from action_engine import execute_action
    from verification.verification_engine import verify_action

We intentionally DO NOT modify the existing pipeline files.

This API entry point:

1. Preserves legacy import compatibility.
2. Exposes the existing recovery pipeline through FastAPI.
3. Provides health and root endpoints.
4. Serves the frontend from the /frontend directory.
5. Keeps the existing 429 tests and CLI simulation unchanged.
"""


# ============================================================
# IMPORTS
# ============================================================

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


# ============================================================
# PROJECT PATHS
# ============================================================

# Current file:
#
# E:\ReviveAI\src\api\main.py
#
# parents[0] -> E:\ReviveAI\src\api
# parents[1] -> E:\ReviveAI\src
# parents[2] -> E:\ReviveAI

SRC_DIR = Path(__file__).resolve().parents[1]

PROJECT_DIR = SRC_DIR.parent

FRONTEND_DIR = PROJECT_DIR / "frontend"


# ============================================================
# LEGACY IMPORT COMPATIBILITY
# ============================================================

"""
The existing ReviveAI pipeline uses legacy absolute imports.

For example:

    from risk_detector import detect_risk

But the actual file is:

    src/risk_model/risk_detector.py

Therefore Python needs to search the following directories.

We add these directories to sys.path BEFORE importing
the existing orchestrator.

IMPORTANT:

We do NOT modify the existing pipeline files.
"""


COMPATIBILITY_DIRS = [

    # Main src directory
    SRC_DIR,

    # Risk detection
    SRC_DIR / "risk_model",

    # Diagnosis
    SRC_DIR / "diagnosis",

    # Policy
    SRC_DIR / "policy",

    # Actions
    SRC_DIR / "actions",

    # Verification
    SRC_DIR / "verification",

    # Pipeline
    SRC_DIR / "pipeline",

    # Project root
    PROJECT_DIR,
]


for directory in COMPATIBILITY_DIRS:

    directory = directory.resolve()

    if directory.exists():

        directory_string = str(directory)

        if directory_string not in sys.path:

            sys.path.insert(
                0,
                directory_string,
            )


# ============================================================
# COMPATIBILITY CHECK
# ============================================================

"""
Verify that the important legacy module exists.

Expected location:

    E:\ReviveAI\src\risk_model\risk_detector.py

If this file is missing, startup should fail with a clear
error instead of producing a confusing import error.
"""


RISK_DETECTOR_PATH = (
    SRC_DIR
    / "risk_model"
    / "risk_detector.py"
)


if not RISK_DETECTOR_PATH.exists():

    raise RuntimeError(
        "ReviveAI compatibility error: "
        f"risk_detector.py was not found at "
        f"{RISK_DETECTOR_PATH}"
    )


# ============================================================
# EXISTING PIPELINE
# ============================================================

"""
IMPORTANT:

The compatibility paths MUST be configured before this import.

This imports the existing working ReviveAI pipeline.

We are NOT rewriting the pipeline.
"""

from src.pipeline.orchestrator import run_pipeline


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(

    title="ReviveAI API",

    description=(
        "Revenue recovery decision API built on top of "
        "the existing ReviveAI recovery pipeline."
    ),

    version="1.0.0",
)
# ============================================================
# CORS CONFIGURATION
# ============================================================

app.add_middleware(
    CORSMiddleware,

    # Frontend development server
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],

    allow_credentials=True,

    allow_methods=[
        "*"
    ],

    allow_headers=[
        "*"
    ],
)


# ============================================================
# STATIC FRONTEND
# ============================================================

"""
Frontend location:

    E:\ReviveAI\frontend

Static assets can be accessed through:

    /static/...

For example:

    /static/style.css
    /static/app.js
"""


if FRONTEND_DIR.exists():

    app.mount(

        "/static",

        StaticFiles(
            directory=str(FRONTEND_DIR)
        ),

        name="static",
    )


# ============================================================
# REQUEST MODEL
# ============================================================

class PaymentRequest(BaseModel):

    """
    Payment event accepted by ReviveAI.

    transaction_id is mandatory.

    The remaining fields are optional so the API remains
    compatible with the existing pipeline.
    """

    # --------------------------------------------------------
    # Transaction information
    # --------------------------------------------------------

    transaction_id: str = Field(

        ...,

        min_length=1,

        description="Unique payment transaction ID",
    )

    amount: float = Field(

        default=0.0,

        ge=0,

        description="Payment amount at risk",
    )

    # --------------------------------------------------------
    # Customer / payment information
    # --------------------------------------------------------

    payment_method: str | None = None

    customer_type: str | None = None

    customer_age_days: int | None = None

    previous_transactions: int | None = None

    previous_success_rate: float | None = None

    # --------------------------------------------------------
    # Failure information
    # --------------------------------------------------------

    failure_code: str | None = None

    failure_type: str | None = None

    attempt_count: int | None = None

    time_since_failure_min: float | None = None

    # --------------------------------------------------------
    # Temporal information
    # --------------------------------------------------------

    hour_of_day: int | None = None

    is_weekend: int | bool | None = None

    # --------------------------------------------------------
    # Optional simulation / evaluation fields
    # --------------------------------------------------------

    actual_recovery: (
        bool
        | str
        | int
        | float
        | None
    ) = None

    recovered_amount: float | None = Field(

        default=None,

        ge=0,
    )


# ============================================================
# ROOT ENDPOINT
# ============================================================

@app.get(
    "/",
    include_in_schema=False,
)
def root() -> dict[str, Any]:

    """
    Root endpoint.

    If the frontend exists, return index.html.

    Otherwise return API status information.
    """

    index_file = FRONTEND_DIR / "index.html"

    if index_file.exists():

        return FileResponse(

            str(index_file),

            media_type="text/html",
        )

    return {

        "service": "ReviveAI",

        "status": "running",

        "message": (
            "ReviveAI API is operational."
        ),

        "version": "1.0.0",
    }


# ============================================================
# HEALTH ENDPOINT
# ============================================================

@app.get("/health")
def health() -> dict[str, str]:

    """
    Health check endpoint.

    Used to confirm that the FastAPI application is running.
    """

    return {

        "status": "healthy",
    }


# ============================================================
# RECOVERY ENDPOINT
# ============================================================

@app.post("/api/v1/recover")
def recover_payment(
    payment: PaymentRequest,
) -> dict[str, Any]:

    """
    Send a payment through the existing ReviveAI pipeline.

    Pipeline:

        Payment Request
              |
              v
        Risk Detection
              |
              v
        Diagnosis
              |
              v
        Policy / Guardrails
              |
              v
        Action
              |
              v
        Verification
              |
              v
        API Response
    """

    # --------------------------------------------------------
    # Convert Pydantic model to dictionary
    # --------------------------------------------------------

    payment_data = payment.model_dump(

        exclude_none=True,
    )

    # --------------------------------------------------------
    # Execute existing ReviveAI pipeline
    # --------------------------------------------------------

    try:

        result = run_pipeline(

            payment_data,
        )

        return {

            "status": "success",

            "transaction_id":
                payment.transaction_id,

            "result":
                result,
        }

    # --------------------------------------------------------
    # Pipeline validation errors
    # --------------------------------------------------------

    except (
        ValueError,
        TypeError,
    ) as error:

        raise HTTPException(

            status_code=400,

            detail={

                "error_type":
                    type(error).__name__,

                "message":
                    str(error),
            },
        ) from error

    # --------------------------------------------------------
    # Unexpected errors
    # --------------------------------------------------------

    except Exception as error:

        raise HTTPException(

            status_code=500,

            detail={

                "error_type":
                    type(error).__name__,

                "message":
                    str(error),
            },
        ) from error


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(

        "src.api.main:app",

        host="127.0.0.1",

        port=8000,

        reload=True,
    )