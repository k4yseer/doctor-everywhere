# Payment Wrapper Microservice

A thin atomic service that wraps the Stripe API. It is called by the **Make Payment** orchestrator to create and immediately **confirm** a Stripe PaymentIntent server-side, then returns the final payment status.

## How it fits into the payment flow

```
Patient UI  →  API Gateway  →  Make Payment (orchestrator)
                                     │
                              3. POST /api/wrapper/stripe/charge
                                     │
                              Stripe Payment Wrapper  →  Stripe API
                                     │
                              success / failure
                                     │
                    Make Payment publishes PAYMENT_SUCCESSFUL to AMQP
```

The frontend collects card details via Stripe.js **before** the payment request is sent. Stripe.js returns a `paymentMethodId`, which the client includes in its call to the API Gateway. The orchestrator forwards this ID to the wrapper, which completes the charge entirely server-side.

## Environment Variables

Add these to `backend/.env`:

```
STRIPE_SECRET_KEY=sk_test_...
PORT=5005
```

| Variable | Description |
|---|---|
| `STRIPE_SECRET_KEY` | Your Stripe secret key (test or live) |
| `PORT` | Port the service listens on (default: `5005`) |

## Running

**Via Docker Compose** (from `backend/`):

```bash
docker compose up --build payment-wrapper
```

**Locally:**

```bash
pip install -r requirements.txt
python app/main.py
```

The service starts on `http://localhost:5005`.

## API

### `POST /api/wrapper/stripe/charge`

Creates and immediately confirms a Stripe PaymentIntent server-side.

**Request body (JSON)**

| Field | Type | Required | Description |
|---|---|---|---|
| `amount` | integer | Yes | Amount in the **smallest currency unit** (e.g. cents — `5000` = SGD 50.00) |
| `currency` | string | Yes | Three-letter ISO currency code (e.g. `"sgd"`) |
| `paymentMethodId` | string | Yes | Stripe PaymentMethod ID from Stripe.js (e.g. `"pm_card_visa"`) |

**Example request**

```json
{
  "amount": 5000,
  "currency": "sgd",
  "paymentMethodId": "pm_card_visa"
}
```

**Success — `200 OK`**

```json
{
  "success": true,
  "transactionId": "pi_3Abc...",
  "status": "succeeded"
}
```

**Payment declined — `402 Payment Required`**

```json
{
  "success": false,
  "transactionId": "pi_3Abc...",
  "status": "declined",
  "error": "Your card was declined."
}
```

**Missing fields — `400 Bad Request`**

```json
{
  "success": false,
  "error": "Missing required fields: 'amount', 'currency', and 'paymentMethodId'"
}
```

**Gateway error — `500 Internal Server Error`**

```json
{
  "success": false,
  "error": "Payment processing failed at the gateway."
}
```

> **Note:** On any non-200 response, the Make Payment orchestrator is responsible for publishing a `SYSTEM_ERROR` event to the AMQP message broker.

## API Documentation (Swagger)

```
http://localhost:5005/apidocs
```
