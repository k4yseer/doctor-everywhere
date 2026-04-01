import os
from typing import Optional

import requests
import strawberry
from flask import Flask, jsonify, request
from strawberry.flask.views import GraphQLView
from werkzeug.exceptions import HTTPException

from app.error_publisher import publish_error as _publish_error

app = Flask(__name__)

SERVICE_NAME = "consultation-orchestrator"

# Required environment variables/defaults from spec.
APPOINTMENT_URL = os.environ.get("appointmentURL", "http://appointment-service:5002")
INVOICE_URL = os.environ.get("invoiceURL", "http://invoice-service:5005")
DELIVERY_URL = os.environ.get("deliveryURL", "http://delivery-service:5006")
PRESCRIPTION_URL = os.environ.get(
    "prescriptionURL",
    "https://personal-pehihv0m.outsystemscloud.com/ESDPrescriptionService/rest/PrescriptionAPI",
)

TIMEOUT_SECONDS = 5


def error_response(status_code, message, error_code, payload=None):
    if status_code >= 500:
        _publish_error(
            source_service=SERVICE_NAME,
            error_code=error_code,
            error_message=message,
            payload=payload,
        )
    return jsonify({"code": status_code, "message": message}), status_code


@app.errorhandler(Exception)
def handle_unexpected_error(err):
    if isinstance(err, HTTPException):
        return error_response(
            err.code or 500,
            err.description,
            f"CONSULT-HISTORY-{err.code or 500}-HTTP",
            {"path": request.path, "method": request.method},
        )

    return error_response(
        500,
        "Internal server error",
        "CONSULT-HISTORY-500-UNHANDLED",
        {"path": request.path, "method": request.method, "error": str(err)},
    )


def _safe_get(url, params=None):
    try:
        return requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
    except requests.RequestException:
        return None


def _extract_data(body):
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


def _friendly_status(raw_status):
    if not raw_status:
        return "Pending"
    text = str(raw_status).strip().replace("_", " ")
    return " ".join(word.capitalize() for word in text.split())


def _default_mc():
    return {"has_mc": False, "start_date": None, "duration_days": 0}


def _default_billing():
    return {"amount": 0.0, "payment_status": "Pending", "delivery_status": "Pending"}


def _extract_prescription_block(appointment_id):
    mc = _default_mc()
    prescriptions = []

    # Required endpoint from spec.
    res = _safe_get(f"{PRESCRIPTION_URL}/GetPrescription", params={"AppointmentId": appointment_id})
    if not res or res.status_code == 404:
        return mc, prescriptions
    if res.status_code >= 400:
        return mc, prescriptions

    try:
        payload = _extract_data(res.json())
    except ValueError:
        return mc, prescriptions

    rows = payload if isinstance(payload, list) else [payload]

    for row in rows:
        if not isinstance(row, dict):
            continue

        # Common MC key patterns for varied upstream payloads.
        has_mc = row.get("has_mc")
        if has_mc is None:
            has_mc = row.get("hasMC")
        if has_mc is None and (row.get("mc_start_date") or row.get("mcStartDate")):
            has_mc = True

        if has_mc is not None:
            mc["has_mc"] = bool(has_mc)

        mc_start = row.get("start_date") or row.get("mc_start_date") or row.get("mcStartDate")
        if mc_start:
            mc["start_date"] = mc_start

        duration = row.get("duration_days") or row.get("mc_duration_days") or row.get("mcDurationDays")
        if duration is not None:
            try:
                mc["duration_days"] = int(duration)
            except (TypeError, ValueError):
                pass

        drug_name = row.get("drug_name") or row.get("drugName") or row.get("medicine_name") or row.get("name")
        quantity = row.get("quantity") or row.get("qty")

        if drug_name:
            try:
                qty_val = int(quantity) if quantity is not None else 0
            except (TypeError, ValueError):
                qty_val = 0
            prescriptions.append({"drug_name": str(drug_name), "quantity": qty_val})

    return mc, prescriptions


def _extract_invoice_block(appointment_id):
    billing = _default_billing()
    invoice_id = None

    # Required endpoint from spec.
    res = _safe_get(f"{INVOICE_URL}/invoices/appointment/{appointment_id}")
    # Fallback to currently implemented atomic invoice endpoint.
    if res and res.status_code == 404:
        res = _safe_get(f"{INVOICE_URL}/invoices/{appointment_id}")

    if not res or res.status_code == 404:
        return billing, invoice_id
    if res.status_code >= 400:
        return billing, invoice_id

    try:
        payload = _extract_data(res.json())
    except ValueError:
        return billing, invoice_id

    if isinstance(payload, dict):
        amount = payload.get("amount", 0)
        try:
            billing["amount"] = float(amount)
        except (TypeError, ValueError):
            billing["amount"] = 0.0

        billing["payment_status"] = payload.get("payment_status", "Pending")
        invoice_id = payload.get("invoice_id")

    return billing, invoice_id


def _extract_delivery_status(appointment_id, patient_id, invoice_id):
    # Required endpoint from spec.
    res = _safe_get(f"{DELIVERY_URL}/deliveries/appointment/{appointment_id}")

    # Optional route mentioned in spec.
    if res and res.status_code == 404 and invoice_id:
        res = _safe_get(f"{DELIVERY_URL}/deliveries/invoice/{invoice_id}")

    # Fallback to current atomic delivery implementation.
    if res and res.status_code == 404:
        res = _safe_get(f"{DELIVERY_URL}/deliveries/{patient_id}", params={"appointment_id": appointment_id})

    if not res or res.status_code == 404 or res.status_code >= 400:
        return "Pending"

    try:
        payload = _extract_data(res.json())
    except ValueError:
        return "Pending"

    if isinstance(payload, list) and payload:
        row = payload[0]
        if isinstance(row, dict):
            return row.get("delivery_status", "Pending")

    if isinstance(payload, dict):
        return payload.get("delivery_status", "Pending")

    return "Pending"


# Legacy REST rollback reference (disabled).
# @app.route("/consultation-history/<int:patient_id>", methods=["GET"])
# def get_consultation_history(patient_id):
#     # Step 1: Required appointment endpoint from spec.
#     appointment_res = _safe_get(f"{APPOINTMENT_URL}/appointments/patient/{patient_id}")
#
#     # Step 2: On error/404, safely return empty list with 200.
#     if not appointment_res or appointment_res.status_code == 404 or appointment_res.status_code >= 400:
#         return jsonify([]), 200
#
#     try:
#         appt_payload = _extract_data(appointment_res.json())
#     except ValueError:
#         return jsonify([]), 200
#
#     appointments = appt_payload if isinstance(appt_payload, list) else []
#     history_list = []
#
#     # Step 4 + 5 + 6
#     for appt in appointments:
#         if not isinstance(appt, dict):
#             continue
#
#         appointment_id = appt.get("appointment_id", appt.get("id"))
#         if appointment_id is None:
#             continue
#
#         appt_date = appt.get("date") or appt.get("slot_datetime")
#         appt_status = _friendly_status(appt.get("status"))
#         appt_patient_id = appt.get("patient_id", patient_id)
#
#         mc, prescriptions = _extract_prescription_block(appointment_id)
#         billing, invoice_id = _extract_invoice_block(appointment_id)
#         billing["delivery_status"] = _extract_delivery_status(appointment_id, appt_patient_id, invoice_id)
#
#         history_list.append(
#             {
#                 "appointment_id": appointment_id,
#                 "date": appt_date,
#                 "status": appt_status,
#                 "mc": mc,
#                 "prescriptions": prescriptions,
#                 "billing": billing,
#             }
#         )
#
#     return jsonify(history_list), 200


@strawberry.type
class MC:
    has_mc: bool
    start_date: Optional[str]
    duration_days: int


@strawberry.type
class Prescription:
    drug_name: str
    quantity: int


@strawberry.type
class Billing:
    amount: float
    payment_status: str
    delivery_status: str


@strawberry.type
class Appointment:
    appointment_id: int
    date: Optional[str]
    status: str
    clinical_notes: Optional[str]
    _patient_id: strawberry.Private[int]
    _mc_cache: strawberry.Private[Optional[MC]] = None
    _prescriptions_cache: strawberry.Private[Optional[list[Prescription]]] = None
    _billing_cache: strawberry.Private[Optional[Billing]] = None

    @strawberry.field
    def mc(self) -> MC:
        if self._mc_cache is not None:
            return self._mc_cache

        mc_block, prescriptions_block = _extract_prescription_block(self.appointment_id)
        self._mc_cache = MC(
            has_mc=bool(mc_block.get("has_mc", False)),
            start_date=mc_block.get("start_date"),
            duration_days=int(mc_block.get("duration_days", 0)),
        )
        self._prescriptions_cache = [
            Prescription(
                drug_name=str(item.get("drug_name", "")),
                quantity=int(item.get("quantity", 0)),
            )
            for item in prescriptions_block
            if isinstance(item, dict) and item.get("drug_name")
        ]
        return self._mc_cache

    @strawberry.field
    def prescriptions(self) -> list[Prescription]:
        if self._prescriptions_cache is not None:
            return self._prescriptions_cache

        mc_block, prescriptions_block = _extract_prescription_block(self.appointment_id)
        self._mc_cache = MC(
            has_mc=bool(mc_block.get("has_mc", False)),
            start_date=mc_block.get("start_date"),
            duration_days=int(mc_block.get("duration_days", 0)),
        )
        self._prescriptions_cache = [
            Prescription(
                drug_name=str(item.get("drug_name", "")),
                quantity=int(item.get("quantity", 0)),
            )
            for item in prescriptions_block
            if isinstance(item, dict) and item.get("drug_name")
        ]
        return self._prescriptions_cache

    @strawberry.field
    def billing(self) -> Billing:
        if self._billing_cache is not None:
            return self._billing_cache

        billing_block, invoice_id = _extract_invoice_block(self.appointment_id)
        billing_block["delivery_status"] = _extract_delivery_status(
            self.appointment_id,
            self._patient_id,
            invoice_id,
        )
        self._billing_cache = Billing(
            amount=float(billing_block.get("amount", 0.0)),
            payment_status=str(billing_block.get("payment_status", "Pending")),
            delivery_status=str(billing_block.get("delivery_status", "Pending")),
        )
        return self._billing_cache


@strawberry.type
class Query:
    @strawberry.field
    def consultation_history(self, patient_id: int) -> list[Appointment]:
        # Main/base call only: appointment service.
        appointment_res = _safe_get(f"{APPOINTMENT_URL}/appointments/patient/{patient_id}")

        # Preserve existing behavior: return empty list on 404/errors.
        if not appointment_res or appointment_res.status_code == 404 or appointment_res.status_code >= 400:
            return []

        try:
            appt_payload = _extract_data(appointment_res.json())
        except ValueError:
            return []

        appointments = appt_payload if isinstance(appt_payload, list) else []
        history_list: list[Appointment] = []

        for appt in appointments:
            if not isinstance(appt, dict):
                continue

            appointment_id = appt.get("appointment_id", appt.get("id"))
            if appointment_id is None:
                continue

            try:
                appointment_id_int = int(appointment_id)
            except (TypeError, ValueError):
                continue

            raw_patient_id = appt.get("patient_id", patient_id)
            try:
                appt_patient_id = int(raw_patient_id)
            except (TypeError, ValueError):
                appt_patient_id = patient_id

            history_list.append(
                Appointment(
                    appointment_id=appointment_id_int,
                    date=appt.get("date") or appt.get("slot_datetime"),
                    status=_friendly_status(appt.get("status")),
                    clinical_notes=appt.get("clinical_notes"),
                    _patient_id=appt_patient_id,
                )
            )

        return history_list


schema = strawberry.Schema(query=Query)
app.add_url_rule(
    "/graphql",
    view_func=GraphQLView.as_view("graphql_view", schema=schema),
)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5013, debug=True)
