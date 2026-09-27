# Sample Shop API

A tiny FastAPI service used as the demo target for **API Contract Guardian**.

## Run it

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Checkout example

Consumer #3: this doc. Nobody updates curl examples in READMEs, which
is exactly why they're a good demo of context a plain diff tool misses.

```bash
curl -X POST http://localhost:8000/checkout \
  -H "Content-Type: application/json" \
  -d '{"cart_id": "cart_1"}'

# {
#   "order_id": "ord_12345",
#   "total_amount": 42.50,
#   "currency": "USD"
# }
```
