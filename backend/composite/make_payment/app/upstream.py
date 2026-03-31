import os
import requests

STRIPE_WRAPPER_URL = os.getenv("STRIPE_WRAPPER_URL", "http://payment-wrapper:5005")
INVOICE_SERVICE_URL = os.getenv("INVOICE_SERVICE_URL", "http://invoice-service:5008")
APPOINTMENT_SERVICE_URL = os.getenv("APPOINTMENT_SERVICE_URL", "http://appointment-service:5002")
DELIVERY_SERVICE_URL = os.getenv("DELIVERY_SERVICE_URL", "http://delivery-service:5014")
INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://inventory-service:5009")
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


def create_invoice(appointment_id, patient_id, amount, currency, transaction_id):
    try:
        res = requests.post(
            f"{INVOICE_SERVICE_URL}/invoices/{appointment_id}",
            json={
                "patient_id": patient_id,
                "amount": amount / 100.0,
                "currency": currency,
                "payment_status": "PAID",
                "stripe_charge_id": transaction_id,
            },
            timeout=10,
        )
    except requests.exceptions.RequestException:
        _raise_for_connection("Invoice service", "MAKE-PAYMENT-503-INVOICE_UNREACHABLE")

    if res.status_code not in (200, 201):
        message = _get_error_message(res, "Invoice creation failed")
        raise UpstreamError(res.status_code, message, f"MAKE-PAYMENT-{res.status_code}-INVOICE")

    return res.json().get("data", {})


def update_appointment_status(appointment_id, status="PAID"):
    try:
        res = requests.put(
            f"{APPOINTMENT_SERVICE_URL}/appointments/{appointment_id}/status",
            json={"status": status},
            timeout=10,
        )
    except requests.exceptions.RequestException:
        _raise_for_connection("Appointment service", "MAKE-PAYMENT-503-APPOINTMENT_UNREACHABLE")

    if res.status_code != 200:
        message = _get_error_message(res, "Appointment status update failed")
        raise UpstreamError(res.status_code, message, f"MAKE-PAYMENT-{res.status_code}-APPOINTMENT")

    return res.json().get("data", {})


def create_delivery_order(appointment_id, patient_address):
    try:
        res = requests.post(
            f"{DELIVERY_SERVICE_URL}/deliveries/order",
            json={
                "appointment_id": appointment_id,
                "patient_address": patient_address,
            },
            timeout=10,
        )
    except requests.exceptions.RequestException:
        _raise_for_connection("Delivery service", "MAKE-PAYMENT-503-DELIVERY_UNREACHABLE")

    if res.status_code not in (200, 201):
        message = _get_error_message(res, "Delivery order creation failed")
        raise UpstreamError(res.status_code, message, f"MAKE-PAYMENT-{res.status_code}-DELIVERY")

    return res.json().get("data", {})


def reserve_inventory(medicine_code, appointment_id, amount):
    try:
        res = requests.post(
            f"{INVENTORY_SERVICE_URL}/inventory/reservations/",
            json={
                "medicine_code": medicine_code,
                "appointment_id": appointment_id,
                "amount": amount,
            },
            timeout=10,
        )
    except requests.exceptions.RequestException:
        _raise_for_connection("Inventory service", "MAKE-PAYMENT-503-INVENTORY_UNREACHABLE")

    if res.status_code not in (200, 201):
        message = _get_error_message(res, "Inventory reservation failed")
        raise UpstreamError(res.status_code, message, f"MAKE-PAYMENT-{res.status_code}-INVENTORY")

    return res.json().get("reservation", {})


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
