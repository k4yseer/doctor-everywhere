from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
from werkzeug.exceptions import HTTPException
import pika
import json
import os

from app.error_publisher import publish_error as _publish_error
from app import upstream, notification_publisher
from app.upstream import UpstreamError

app = Flask(__name__)
CORS(app)
Swagger(app)  # Swagger UI at /apidocs

AMQP_URL      = os.environ.get("AMQP_URL", "amqp://guest:guest@rabbitmq:5672/")
EXCHANGE_NAME = "topic_logs"
SERVICE_NAME = "make-payment"


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


# ─── HTTP Helpers ─────────────────────────────────────────────────────────────
def error_response(status_code, message, error_code, payload=None):
    if status_code >= 500:
        _publish_error(source_service=SERVICE_NAME, error_code=error_code, error_message=message, payload=payload)
    return jsonify({"code": status_code, "message": message}), status_code


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
    if not data:
        return error_response(400, "Request body is required", "MAKE-PAYMENT-400-MISSING_BODY")

    appointment_id = data.get("appointment_id")
    patient_id = data.get("patient_id")
    amount = data.get("amount")
    currency = data.get("currency")
    payment_method_id = data.get("paymentMethodId")
    patient_address = data.get("patient_address")
    medicine_code = data.get("medicine_code")
    reserve_amount = data.get("reserve_amount")
    phone_number = data.get("phone_number")

    if not all([appointment_id, patient_id, amount, currency, payment_method_id, patient_address, medicine_code, reserve_amount, phone_number]):
        return error_response(400, "Missing required fields", "MAKE-PAYMENT-400-MISSING_FIELDS")

    transaction_id = upstream.process_payment(amount, currency, payment_method_id)
    invoice_data = upstream.get_invoice(appointment_id)
    if invoice_data:
        invoice_data = upstream.update_invoice_status(appointment_id, transaction_id)
    else:
        invoice_data = upstream.create_invoice(appointment_id, patient_id, amount, currency, transaction_id)
    upstream.update_appointment_status(appointment_id)
    delivery_data = upstream.create_delivery_order(appointment_id, patient_address)
    reservation_data = upstream.reserve_inventory(medicine_code, appointment_id, reserve_amount)

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

    try:
        patient_email = upstream.get_patient_email(patient_id)
        notification_publisher.publish_notification(
            "payment-details",
            {
                "email": patient_email,
                "appointment_id": appointment_id,
                "is_successful": True,
            },
        )
    except Exception as err:
        print(f"[MAKE PAYMENT] WARNING: could not publish payment notification — {err}")

    return jsonify({
        "code": 200,
        "message": "Payment processed successfully",
        "data": {
            "transaction_id": transaction_id,
            "invoice": invoice_data,
            "delivery": delivery_data,
            "reservation": reservation_data,
        },
    }), 200


@app.errorhandler(UpstreamError)
def handle_upstream_error(err):
    return error_response(err.status_code, err.message, err.error_code)


@app.errorhandler(Exception)
def handle_unexpected_error(err):
    if isinstance(err, HTTPException):
        return error_response(
            err.code or 500,
            err.description,
            f"MAKE-PAYMENT-{err.code or 500}-HTTP",
            {"path": request.path, "method": request.method},
        )
    return error_response(
        500,
        "Internal server error",
        "MAKE-PAYMENT-500-UNHANDLED",
        {"path": request.path, "method": request.method, "error": str(err)},
    )


# ─── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5016, debug=True)