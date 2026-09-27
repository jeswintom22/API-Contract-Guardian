"""
Consumer #2: the test suite. This asserts on the exact response
shape of /checkout, so it breaks the moment the field is renamed —
but only if someone remembers to run it before merging.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_checkout_returns_total_amount():
    response = client.post(
        "/checkout",
        json={"cart_id": "cart_1", "coupon_code": None},
    )
    body = response.json()

    assert response.status_code == 200
    assert "total_amount" in body  # <- breaks silently if the field is renamed
    assert body["currency"] == "USD"
