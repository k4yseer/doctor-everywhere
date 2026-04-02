# Make Payment Composite Microservice

This composite service performs payment capture, updates invoice status, and publishes a single downstream event for other services to consume.

## Overview

The service accepts a payment request and performs the following workflow:

1. **Fetch Invoice**: Retrieves the existing invoice for the appointment.
2. **Process Payment**: Calls the Stripe payment wrapper to capture payment.
3. **Update Invoice Status**: Marks the invoice as `PAID`.
4. **Publish payment.success**: Emits a single event to RabbitMQ for downstream consumers.
5. **Publish Notification**: Sends a non-blocking notification request to the notification helper.

## API

### POST /make-payment

Accepts a JSON payload with payment details.

#### Request Body

```json
{
  "appointment_id": 123,
  "patient_id": 456,
  "amount": 5000,
  "currency": "sgd",
  "paymentMethodId": "pm_card_visa",
  "patient_address": "123 Main St, Singapore",
  "phone_number": "+6512345678"
}
```

#### Response

- **200**: Payment processed successfully
- **400**: Missing or invalid fields
- **404**: Invoice not found for appointment
- **500**: Internal service error

## Dependencies

- Payment Wrapper Service
- Invoice Service
- Patient Service (for notification email lookup)
- RabbitMQ (for `payment.success` event)
- Notification helper/service

## Environment Variables

- `AMQP_URL`: RabbitMQ connection URL
- `INVOICE_SERVICE_URL`: URL of the invoice service
- `STRIPE_WRAPPER_URL`: URL of the payment wrapper service
- `PATIENT_SERVICE_URL`: URL of the patient service

## Error Handling

Service-side failures are published to the `topic_logs` exchange under `make_payment.error` and appropriate HTTP error responses are returned.

## Messaging

Publishes a single message to the `topic_logs` exchange:

- `payment.success`: emitted when the payment completes and the invoice is updated

The service also sends a non-blocking notification request to the notification helper for email delivery.