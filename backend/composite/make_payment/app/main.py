from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
import requests
import pika
import json
import os

from app.error_publisher import publish_error as _publish_error

app = Flask(__name__)
CORS(app)
Swagger(app)  # Swagger UI at /apidocs

# ─── Service URLs ──────────────────────────────────────────────────────────────
STRIPE_WRAPPER_URL     = os.environ.get("STRIPE_WRAPPER_URL",     "http://payment-wrapper:5005")
INVOICE_SERVICE_URL    = os.environ.get("INVOICE_SERVICE_URL",    "http://invoice-service:5008")
APPOINTMENT_SERVICE_URL = os.environ.get("APPOINTMENT_SERVICE_URL", "http://appointment-service:5002")
DELIVERY_SERVICE_URL   = os.environ.get("DELIVERY_SERVICE_URL",   "http://delivery-service:5014")
INVENTORY_SERVICE_URL  = os.environ.get("INVENTORY_SERVICE_URL",  "http://inventory-service:5009")

# ─── AMQP Config ───────────────────────────────────────────────────────────────
AMQP_URL      = os.environ.get("AMQP_URL", "amqp://guest:guest@rabbitmq:5672/")
EXCHANGE_NAME = "topic_logs"


# ─── AMQP Helpers ──────────────────────────────────────────────────────────────
def publish_message(routing_key: str, message: dict):
    """Generic AMQP publisher — fire and forget."""
    try:
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        channel    = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=routing_key,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()
        print(f"[MAKE PAYMENT] Published to '{routing_key}'")
    except Exception as e:
        print(f"[MAKE PAYMENT] AMQP publish failed: {e}")


# ─── Main Endpoint ─────────────────────────────────────────────────────────────
@app.route("/make-payment", methods=["POST"])
def make_payment():
    """
    Composite: orchestrate payment processing, invoice creation, status updates, delivery, inventory reservation, and notifications.
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            appointment_id:
              type: integer
            patient_id:
              type: integer
            amount:
              type: integer
              description: Amount in the smallest currency unit (e.g. cents — 5000 = SGD 50.00)
            currency:
              type: string
              example: "sgd"
            paymentMethodId:
              type: string
              description: Stripe PaymentMethod ID
            patient_address:
              type: string
            medicine_code:
              type: string
            reserve_amount:
              type: integer
            phone_number:
              type: string
    responses:
      200:
        description: Payment processed successfully
      400:
        description: Missing required fields or validation error
      500:
        description: Internal service error
    """
    data = request.get_json()

    appointment_id  = data.get("appointment_id")
    patient_id      = data.get("patient_id")
    amount          = data.get("amount")
    currency        = data.get("currency")
    payment_method_id = data.get("paymentMethodId")
    patient_address = data.get("patient_address")
    medicine_code   = data.get("medicine_code")
    reserve_amount  = data.get("reserve_amount")
    phone_number    = data.get("phone_number")

    if not all([appointment_id, patient_id, amount, currency, payment_method_id, patient_address, medicine_code, reserve_amount, phone_number]):
        return jsonify({"code": 400, "message": "Missing required fields"}), 400

    # ── Step 1: Process payment via Stripe wrapper ─────────────────────────────
    try:
        stripe_resp = requests.post(
            f"{STRIPE_WRAPPER_URL}/api/wrapper/stripe/charge",
            json={
                "amount": amount,
                "currency": currency,
                "paymentMethodId": payment_method_id
            },
            timeout=10
        )
        if stripe_resp.status_code not in (200, 201):
            error_msg = stripe_resp.json().get("error", "Stripe payment failed")
            _publish_error("make_payment", f"STRIPE-{stripe_resp.status_code}", error_msg, data)
            return jsonify({"code": stripe_resp.status_code, "message": error_msg}), stripe_resp.status_code

        stripe_data = stripe_resp.json()
        transaction_id = stripe_data.get("transactionId")

    except Exception as e:
        _publish_error("make_payment", "STRIPE-500", str(e), data)
        return jsonify({"code": 500, "message": "Failed to process payment"}), 500

    # ── Step 2: Create invoice ──────────────────────────────────────────────────
    try:
        invoice_resp = requests.post(
            f"{INVOICE_SERVICE_URL}/invoices/{appointment_id}",
            json={
                "patient_id": patient_id,
                "amount": amount / 100.0,  # Convert cents to dollars
                "currency": currency,
                "payment_status": "PAID",
                "stripe_charge_id": transaction_id
            },
            timeout=5
        )
        if invoice_resp.status_code not in (200, 201):
            try:
                error_msg = invoice_resp.json().get("message", invoice_resp.text)
            except Exception:
                error_msg = invoice_resp.text

            _publish_error("make_payment", f"INVOICE-{invoice_resp.status_code}", error_msg, data)
            return jsonify({
                "code": invoice_resp.status_code,
                "message": "Invoice creation failed",
                "details": error_msg 
            }), 500

        invoice_data = invoice_resp.json().get("data", {})

    except Exception as e:
        _publish_error("make_payment", "INVOICE-500", str(e), data)
        return jsonify({
            "code": 500,
            "message": "Failed to create invoice",
            "details": str(e)  # <-- include exception details
        }), 500
    # ── Step 3: Update appointment status to PAID ──────────────────────────────
    try:
        status_resp = requests.put(
            f"{APPOINTMENT_SERVICE_URL}/appointments/{appointment_id}/status",
            json={"status": "PAID"},
            timeout=5
        )
        if status_resp.status_code != 200:
            error_msg = status_resp.json().get("message", "Appointment status update failed")
            _publish_error("make_payment", f"APPT-{status_resp.status_code}", error_msg, data)
            return jsonify({"code": 500, "message": "Failed to update appointment status"}), 500

    except Exception as e:
        _publish_error("make_payment", "APPT-500", str(e), data)
        return jsonify({"code": 500, "message": "Failed to update appointment status"}), 500

    # ── Step 4: Create delivery order ───────────────────────────────────────────
    try:
        delivery_resp = requests.post(
            f"{DELIVERY_SERVICE_URL}/deliveries/order",
            json={
                "appointment_id": appointment_id,
                "patient_address": patient_address
            },
            timeout=5
        )
        if delivery_resp.status_code not in (200, 201):
            error_msg = delivery_resp.json().get("message", "Delivery order creation failed")
            _publish_error("make_payment", f"DELIVERY-{delivery_resp.status_code}", error_msg, data)
            return jsonify({"code": 500, "message": "Failed to create delivery order"}), 500

        delivery_data = delivery_resp.json().get("data", {})

    except Exception as e:
        _publish_error("make_payment", "DELIVERY-500", str(e), data)
        return jsonify({"code": 500, "message": "Failed to create delivery order"}), 500

    # ── Step 5: Create inventory reservation ────────────────────────────────────
    try:
        reserve_resp = requests.post(
            f"{INVENTORY_SERVICE_URL}/inventory/reservations/",
            json={
                "medicine_code": medicine_code,
                "appointment_id": appointment_id,
                "amount": reserve_amount
            },
            timeout=5
        )
        if reserve_resp.status_code not in (200, 201):
            error_msg = reserve_resp.json().get("error", "Inventory reservation failed")
            _publish_error("make_payment", f"INVENTORY-{reserve_resp.status_code}", error_msg, data)
            return jsonify({"code": 500, "message": "Failed to reserve inventory"}), 500

        reservation_data = reserve_resp.json().get("reservation", {})

    except Exception as e:
        _publish_error("make_payment", "INVENTORY-500", str(e), data)
        return jsonify({"code": 500, "message": "Failed to reserve inventory"}), 500

    # ── Step 6: Publish AMQP messages ───────────────────────────────────────────
    publish_message(
        routing_key="appointment.complete",
        message={"appointment_id": appointment_id}
    )

    publish_message(
        routing_key="delivery.create",
        message={"appointment_id": appointment_id, "delivery_id": delivery_data.get("delivery_id")}
    )

    publish_message(
        routing_key="inventory.reserved",
        message={"appointment_id": appointment_id, "reservation_id": reservation_data.get("reservation_id")}
    )

    publish_message(
        routing_key="twilio.sms",
        message={
            "phone_number": phone_number,
            "text": f"Payment successful for appointment {appointment_id}. Your order is being prepared."
        }
    )

    return jsonify({
        "code": 200,
        "message": "Payment processed successfully",
        "data": {
            "transaction_id": transaction_id,
            "invoice": invoice_data,
            "delivery": delivery_data,
            "reservation": reservation_data
        }
    }), 200


# ─── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5016, debug=True)