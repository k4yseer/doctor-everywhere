from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
from werkzeug.exceptions import HTTPException
import pika
import json
import os
import uuid
from decimal import Decimal, InvalidOperation

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
    connection = None
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
        app.logger.info(f"Published to '{routing_key}'")
    except Exception as e:
        app.logger.error(f"[AMQP] publish failed: {str(e)}", exc_info=True)
    finally:
        if connection and connection.is_open:
            connection.close()


# ─── HTTP Helpers ─────────────────────────────────────────────────────────────
def error_response(status_code, message, error_code, payload=None):
    if status_code >= 500:
        _publish_error(source_service=SERVICE_NAME, error_code=error_code, error_message=message, payload=payload)
    return jsonify({"code": status_code, "message": message}), status_code


def _log_step(correlation_id: str, message: str):
    app.logger.info(f"[{correlation_id}] {message}")


@app.route("/make-payment", methods=["POST"])
def make_payment():
    """
    Composite: fetch invoice, process payment, update invoice status, and emit payment.success.
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
              type: number
              format: float
              description: Amount in dollars (e.g. 50.00)
            currency:
              type: string
              example: "sgd"
            paymentMethodId:
              type: string
              description: Stripe PaymentMethod ID
            patient_address:
              type: string
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
    correlation_id = str(uuid.uuid4())
    _log_step(correlation_id, "Received make-payment request")
    if not data:
        return error_response(400, "Request body is required", "MAKE-PAYMENT-400-MISSING_BODY")

    appointment_id = data.get("appointment_id")
    patient_id = data.get("patient_id")
    amount = data.get("amount")
    currency = data.get("currency")
    payment_method_id = data.get("paymentMethodId")
    patient_address = data.get("patient_address")
    phone_number = data.get("phone_number")

    # Legacy reservation and downstream orchestration removed from this service.
    # Inventory reservation and invoice creation happens in make-prescription.

    if appointment_id is None or patient_id is None:
        _log_step(correlation_id, "Missing required appointment_id or patient_id")
        return error_response(400, "appointment_id and patient_id are required", "MAKE-PAYMENT-400-MISSING_FIELDS", {"correlation_id": correlation_id})

    invoice_data = upstream.get_invoice(appointment_id)
    if not invoice_data:
        _log_step(correlation_id, f"Invoice not found for appointment_id={appointment_id}")
        return error_response(404, f"Invoice not found for appointment_id {appointment_id}", "MAKE-PAYMENT-404-INVOICE_MISSING", {"correlation_id": correlation_id})
    if str(invoice_data.get("payment_status", "")).upper() == "PAID":
        _log_step(correlation_id, "Payment already completed, skipping charge")
        return jsonify({
            "code": 200,
            "message": "Payment already processed",
            "data": {
                "transaction_id": invoice_data.get("stripe_charge_id"),
                "invoice": invoice_data,
            },
            "correlation_id": correlation_id,
        }), 200

    _log_step(correlation_id, f"Fetched invoice for appointment_id={appointment_id}")

    if amount is None:
        invoice_amount = invoice_data.get("amount")
        if invoice_amount is None:
            _log_step(correlation_id, "Amount not provided and invoice amount missing")
            return error_response(400, "Amount is required either in request or invoice", "MAKE-PAYMENT-400-MISSING_AMOUNT", {"correlation_id": correlation_id})
    else:
        invoice_amount = amount
    try:
        amount = int((Decimal(str(invoice_amount)) * 100).to_integral_value())
        if amount <= 0:
            _log_step(correlation_id, "Invalid amount <= 0")
            return error_response(400, "Amount must be greater than 0", "MAKE-PAYMENT-400-INVALID_AMOUNT", {"correlation_id": correlation_id})
    except (InvalidOperation, TypeError, ValueError):
        _log_step(correlation_id, "Invalid invoice amount")
        return error_response(400, "Invalid invoice amount", "MAKE-PAYMENT-400-INVOICE_AMOUNT_INVALID", {"correlation_id": correlation_id})


    if not payment_method_id:
        _log_step(correlation_id, "Missing paymentMethodId")
        return error_response(400, "paymentMethodId is required", "MAKE-PAYMENT-400-MISSING_PAYMENT_METHOD", {"correlation_id": correlation_id})

    if not currency:
        currency = invoice_data.get("currency")
    if currency:
        currency = currency.lower()
    if not currency:
        _log_step(correlation_id, "Currency is required")
        return error_response(400, "Currency is required", "MAKE-PAYMENT-400-MISSING_CURRENCY", {"correlation_id": correlation_id})

    _log_step(correlation_id, f"Processing payment for appointment_id={appointment_id}, amount={amount}, currency={currency}")
    idempotency_key = f"payment:{appointment_id}:{payment_method_id}"
    transaction_id = upstream.process_payment(amount, currency, payment_method_id, idempotency_key)
    _log_step(correlation_id, f"Payment processed transaction_id={transaction_id}")

    updated_invoice = upstream.update_invoice_status(appointment_id, transaction_id)
    _log_step(correlation_id, f"Invoice updated to PAID for appointment_id={appointment_id}")

    event_payload = {
        "event_type": "payment.success",
        "version": "v2",
        "correlation_id": correlation_id,
        "appointment_id": appointment_id,
        "patient_id": patient_id,
        "transaction_id": transaction_id,
        "amount": amount,
        "currency": currency,
        "phone_number": phone_number,
        "patient_address": patient_address,
    }

    try:
        publish_message("payment.success", event_payload)
        _log_step(correlation_id, "Published payment.success event")
    except Exception as err:
        _log_step(correlation_id, f"Failed to publish payment.success event: {err}")

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
        _log_step(correlation_id, "Published email notification")
    except Exception as err:
        _log_step(correlation_id, f"Non-blocking notification failure: {err}")

    return jsonify({
        "code": 200,
        "message": "Payment processed successfully",
        "data": {
            "transaction_id": transaction_id,
            "invoice": updated_invoice,
        },
        "correlation_id": correlation_id,
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