"""
Sample target application — a small FastAPI service used as the demo
"patient" for API Contract Guardian. This file represents the BEFORE
state. The hackathon demo introduces a breaking change to the
/checkout endpoint on a second commit/branch and shows Guardian
catching every consumer that change silently breaks.
"""
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Sample Shop API")


class CheckoutRequest(BaseModel):
    cart_id: str
    coupon_code: str | None = None


class CheckoutResponse(BaseModel):
    order_id: str
    total: float
    currency: str


@app.post("/checkout", response_model=CheckoutResponse)
def checkout(payload: CheckoutRequest) -> CheckoutResponse:
    """
    Finalize a cart into an order.

    NOTE for the demo: the response field gets renamed on the
    "breaking-change" branch (see setup_demo.sh). That single rename
    is what Guardian is meant to catch across the rest of the repo.
    """
    return CheckoutResponse(order_id="ord_12345", total=42.50, currency="USD")


@app.get("/users/{user_id}")
def get_user(user_id: str) -> dict:
    return {"user_id": user_id, "name": "Jane Doe", "email": "jane@example.com"}
