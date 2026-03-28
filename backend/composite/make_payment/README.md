# Make Payment Composite Microservice

This composite service orchestrates the payment processing workflow, integrating with multiple atomic services to handle payments, invoicing, status updates, delivery, and inventory management.

## Overview

The service accepts a payment request and performs the following steps in sequence:

1. **Process Payment**: Calls the Stripe payment wrapper to charge the payment method.
2. **Create Invoice**: Records the payment in the invoice service.
3. **Update Appointment Status**: Sets the appointment status to "PAID".
4. **Create Delivery Order**: Initiates a delivery order for the patient.
5. **Reserve Inventory**: Reserves the specified medicine in inventory.
6. **Publish Notifications**: Sends AMQP messages for downstream processing and SMS notifications.

## API

### POST /make-payment

Accepts a JSON payload with payment details and orchestrates the entire workflow.

#### Request Body

```json
{
  "appointment_id": 123,
  "patient_id": 456,
  "amount": 5000,
  "currency": "sgd",
  "paymentMethodId": "pm_card_visa",
  "patient_address": "123 Main St, Singapore",
  "medicine_code": "MED001",
  "reserve_amount": 10,
  "phone_number": "+6512345678"
}
```

#### Response

- **200**: Payment processed successfully
- **400**: Missing or invalid fields
- **500**: Internal service error

## Dependencies

- Payment Wrapper Service (Stripe integration)
- Invoice Service
- Appointment Service
- Delivery Service
- Inventory Service
- RabbitMQ (for messaging)

## Environment Variables

- `STRIPE_WRAPPER_URL`: URL of the payment wrapper service
- `INVOICE_SERVICE_URL`: URL of the invoice service
- `APPOINTMENT_SERVICE_URL`: URL of the appointment service
- `DELIVERY_SERVICE_URL`: URL of the delivery service
- `INVENTORY_SERVICE_URL`: URL of the inventory service
- `AMQP_URL`: RabbitMQ connection URL

## Error Handling

Errors are published to the `topic_logs` exchange with routing key `make_payment.error`. The service continues processing where possible but returns appropriate error responses.

## Messaging

Publishes messages to the `topic_logs` exchange:

- `appointment.complete`: Notifies appointment completion
- `delivery.create`: Triggers delivery processing
- `inventory.reserved`: Confirms inventory reservation
- `twilio.sms`: Sends SMS notification to patient