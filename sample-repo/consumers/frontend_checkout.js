// Consumer #1: frontend checkout flow.
// Calls POST /checkout and reads `total_amount` off the response to
// render the order confirmation screen.

async function completeCheckout(cartId, couponCode) {
  const res = await fetch("/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cart_id: cartId, coupon_code: couponCode }),
  });

  const data = await res.json();

  renderConfirmation({
    orderId: data.order_id,
    amount: data.total_amount, // <- breaks silently if the field is renamed
    currency: data.currency,
  });
}

function renderConfirmation({ orderId, amount, currency }) {
  document.getElementById("order-id").textContent = orderId;
  document.getElementById("order-total").textContent = `${amount} ${currency}`;
}
