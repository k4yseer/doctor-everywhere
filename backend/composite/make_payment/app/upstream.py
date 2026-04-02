import os
import requests

STRIPE_WRAPPER_URL = os.getenv("STRIPE_WRAPPER_URL", "http://payment-wrapper:5005")
INVOICE_SERVICE_URL = os.getenv("INVOICE_SERVICE_URL", "http://invoice-service:5008")
PATIENT_SERVICE_URL = os.getenv("PATIENT_SERVICE_URL", "http://patient-service:5003")


class UpstreamError(Exception):
    def __init__(self, status_code, message, error_code):
        self.status_code = status_code
        self.message = message
        self.error_code = error_code


def _raise_for_connection(service_name, error_code):
    raise UpstreamError(503, f"{service_name} unreachable", error_code)


def _get_error_message(res, fallback="Upstream service error"):
    try:
        return res.json().get("message", fallback)
    except Exception:
        return fallback


def process_payment(amount, currency, payment_method_id):
    try:
        res = requests.post(
            f"{STRIPE_WRAPPER_URL}/api/wrapper/stripe/charge",
            json={
                "amount": amount,
                "currency": currency,
                "paymentMethodId": payment_method_id,
            },
            timeout=10,
        )
    except requests.exceptions.RequestException:
        _raise_for_connection("Stripe wrapper", "MAKE-PAYMENT-503-STRIPE_UNREACHABLE")

    if res.status_code not in (200, 201):
        try:
            body = res.json()
            message = body.get("error") or body.get("message") or "Stripe payment failed"
        except Exception:
            message = "Stripe payment failed"
        raise UpstreamError(res.status_code, message, f"MAKE-PAYMENT-{res.status_code}-STRIPE")

    data = res.json()
    transaction_id = data.get("transactionId")
    if not transaction_id:
        raise UpstreamError(500, "Missing transaction ID from Stripe", "MAKE-PAYMENT-500-STRIPE")

    return transaction_id


def get_invoice(appointment_id):
    try:
        res = requests.get(
            f"{INVOICE_SERVICE_URL}/invoices/{appointment_id}",
            timeout=10,
        )
    except requests.exceptions.RequestException:
        _raise_for_connection("Invoice service", "MAKE-PAYMENT-503-INVOICE_UNREACHABLE")

    if res.status_code == 404:
        return None
    if res.status_code not in (200, 201):
        message = _get_error_message(res, "Invoice lookup failed")
        raise UpstreamError(res.status_code, message, f"MAKE-PAYMENT-{res.status_code}-INVOICE")

    return res.json().get("data", {})


def update_invoice_status(appointment_id, transaction_id, payment_status="PAID"):
    try:
        res = requests.put(
            f"{INVOICE_SERVICE_URL}/invoices/{appointment_id}",
            json={
                "payment_status": payment_status,
                "stripe_charge_id": transaction_id,
            },
            timeout=10,
        )
    except requests.exceptions.RequestException:
        _raise_for_connection("Invoice service", "MAKE-PAYMENT-503-INVOICE_UNREACHABLE")

    if res.status_code not in (200, 201):
        message = _get_error_message(res, "Invoice update failed")
        raise UpstreamError(res.status_code, message, f"MAKE-PAYMENT-{res.status_code}-INVOICE")

    return res.json().get("data", {})

# Legacy invoice creation, appointment update, delivery ordering, and inventory reservation removed.
# This service now only charges payment, updates invoice status, and emits payment.success.


def get_patient_email(patient_id):
    try:
        res = requests.get(
            f"{PATIENT_SERVICE_URL}/patient/{patient_id}/details",
            timeout=10,
        )
    except requests.exceptions.RequestException:
        _raise_for_connection("Patient service", "MAKE-PAYMENT-503-PATIENT_UNREACHABLE")

    if res.status_code != 200:
        message = _get_error_message(res, "Patient lookup failed")
        raise UpstreamError(res.status_code, message, f"MAKE-PAYMENT-{res.status_code}-PATIENT")

    body = res.json()
    email = body.get("data", body).get("email")
    if not email:
        raise UpstreamError(500, "Patient email not available", "MAKE-PAYMENT-500-PATIENT_EMAIL_MISSING")

    return email
