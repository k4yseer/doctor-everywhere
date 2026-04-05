import os
import asyncio
from typing import Optional, List

import httpx
import strawberry
import uvicorn
from strawberry.asgi import GraphQL
from flask import Flask, jsonify, request
from strawberry.flask.views import GraphQLView
from werkzeug.exceptions import HTTPException
from starlette.applications import Starlette
from starlette.routing import Route

from app.error_publisher import publish_error as _publish_error

# app = Flask(__name__)

SERVICE_NAME = "consultation-orchestrator"

# Required environment variables/defaults from spec.
APPOINTMENT_URL = os.environ.get("appointmentURL", "http://appointment-service:5002")
INVOICE_URL = os.environ.get("invoiceURL", "http://invoice-service:5008")
DELIVERY_URL = os.environ.get("deliveryURL", "http://delivery-service:5014")
DOCTOR_URL = os.environ.get("doctorURL", "http://doctor-service:5001")
INVENTORY_URL = os.environ.get("inventoryURL", "http://inventory-service:5009")
PRESCRIPTION_URL = os.environ.get(
    "prescriptionURL",
    "https://personal-pehihv0m.outsystemscloud.com/ESDPrescriptionService/rest/PrescriptionAPI",
)

TIMEOUT_SECONDS = 5


def error_response(status_code, message, error_code, payload=None):
    if status_code >= 400:
        _publish_error(
            source_service=SERVICE_NAME,
            error_code=error_code,
            error_message=message,
            payload=payload,
        )
    return jsonify({"code": status_code, "message": message}), status_code


# @app.errorhandler(Exception)
# def handle_unexpected_error(err):
#     if isinstance(err, HTTPException):
#         return error_response(
#             err.code or 500,
#             err.description,
#             f"CONSULT-HISTORY-{err.code or 500}-HTTP",
#             {"path": request.path, "method": request.method},
#         )

#     return error_response(
#         500,
#         "Internal server error",
#         "CONSULT-HISTORY-500-UNHANDLED",
#         {"path": request.path, "method": request.method, "error": str(err)},
#     )


async def _safe_get_async(client: httpx.AsyncClient, url, params=None):
    try:
        res = await client.get(url, params=params)
        if res.status_code >= 500:
            _publish_error(
                source_service=SERVICE_NAME,
                error_code=f"CONSULT-HISTORY-{res.status_code}-UPSTREAM",
                error_message=f"Upstream service failed: {url} returned {res.status_code}",
                payload={"url": url, "status_code": res.status_code},
            )
        return res
    except httpx.RequestError as exc:
        _publish_error(
            source_service=SERVICE_NAME,
            error_code="CONSULT-HISTORY-UPSTREAM-REQUEST_FAILED",
            error_message=str(exc),
            payload={"url": url},
        )
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
    return {
        "amount": 0.0,
        "consultation_fee": 0.0,
        "medicine_fee": 0.0,
        "payment_status": "Pending",
        "delivery_status": "Pending",
    }


async def _extract_prescription_block_async(client, appointment_id):
    mc = _default_mc()
    prescriptions = []
    normalized_rows = []
    # Required endpoint from spec.
    res = await _safe_get_async(client, f"{PRESCRIPTION_URL}/GetPrescription", params={"AppointmentId": appointment_id})
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

        medicine_code = row.get("medicine_code")
        if not medicine_code:
            continue
        if str(medicine_code).upper() == "MC":
            continue

        medicine_name = row.get("medicine_name")
        quantity = row.get("dispense_quantity")
        if quantity is None:
            quantity = row.get("dispenseQuantity")
        if quantity is None:
            quantity = row.get("quantity")
        if quantity is None:
            quantity = row.get("qty")

        try:
            qty_val = int(quantity) if quantity is not None else 0
        except (TypeError, ValueError):
            qty_val = 0

        dosage = row.get("dosage_instructions") or row.get("dosageInstructions")
        extra_instructions = row.get("instructions")

        raw_unit_price = row.get("unit_price")
        if raw_unit_price is None:
            raw_unit_price = row.get("unitPrice")
        unit_price = None
        if raw_unit_price is not None:
            try:
                unit_price = float(raw_unit_price)
            except (TypeError, ValueError):
                unit_price = None

        raw_total_price = row.get("total_price")
        if raw_total_price is None:
            raw_total_price = row.get("totalPrice")
        if raw_total_price is None:
            raw_total_price = row.get("line_total")
        if raw_total_price is None:
            raw_total_price = row.get("lineTotal")
        line_total = None
        if raw_total_price is not None:
            try:
                line_total = float(raw_total_price)
            except (TypeError, ValueError):
                line_total = None

        if not medicine_name:
            medicine_name = str(medicine_code)

        if medicine_name:
            normalized_rows.append(
                {
                    "medicine_code": str(medicine_code),
                    "medicine_name": str(medicine_name),
                    "quantity": qty_val,
                    "dosage": dosage,
                    "instructions": extra_instructions,
                    "unit_price": unit_price,
                    "line_total": line_total,
                }
            )

    # Consolidate duplicate rows (same medicine + same dosage) into one line item.
    aggregated = {}
    for row in normalized_rows:
        key = (row.get("medicine_code"), row.get("dosage") or "")
        if key not in aggregated:
            aggregated[key] = dict(row)
        else:
            aggregated[key]["quantity"] = int(aggregated[key].get("quantity") or 0) + int(row.get("quantity") or 0)
            existing_total = aggregated[key].get("line_total")
            incoming_total = row.get("line_total")
            if existing_total is not None and incoming_total is not None:
                aggregated[key]["line_total"] = float(existing_total) + float(incoming_total)
            elif existing_total is None:
                aggregated[key]["line_total"] = incoming_total

            if aggregated[key].get("unit_price") is None and row.get("unit_price") is not None:
                aggregated[key]["unit_price"] = row.get("unit_price")

            if not aggregated[key].get("instructions") and row.get("instructions"):
                aggregated[key]["instructions"] = row.get("instructions")

    for row in aggregated.values():
        medicine_code = row.get("medicine_code")
        medicine_name = row.get("medicine_name")
        qty_val = int(row.get("quantity") or 0)
        dosage = row.get("dosage")
        extra_instructions = row.get("instructions")
        unit_price = row.get("unit_price")
        line_total = row.get("line_total")

        if not medicine_name and medicine_code:
            medicine_name = str(medicine_code)

        if medicine_name:
            prescriptions.append(
                {
                    "medicine_code": str(medicine_code) if medicine_code else None,
                    "medicine_name": str(medicine_name),
                    "quantity": qty_val,
                    "dosage": dosage,
                    "instructions": extra_instructions,
                    "unit": "unit(s)",
                    "unit_price": unit_price,
                    "line_total": line_total,
                }
            )

    return mc, prescriptions

async def _extract_doctor_async(client, doctor_id, doctor_cache):
    if not doctor_id:
        return None
    if doctor_id in doctor_cache:
        return doctor_cache[doctor_id]

    res = await _safe_get_async(client, f"{DOCTOR_URL}/doctors/{doctor_id}")

    if not res or res.status_code >= 400:
        return None

    try:
        payload = _extract_data(res.json())
    except ValueError:
        return None

    if not isinstance(payload, dict):
        return None

    result = {
        "id": payload.get("id"),
        "name": payload.get("name"),
        "specialty": payload.get("specialty"),
    }
    doctor_cache[doctor_id] = result
    return result


async def _extract_invoice_block_async(client, appointment_id):
    billing = _default_billing()
    invoice_id = None

    res = await _safe_get_async(client, f"{INVOICE_URL}/invoices/{appointment_id}")

    if not res or res.status_code == 404:
        return billing, invoice_id
    if res.status_code >= 400:
        return billing, invoice_id

    try:
        payload = _extract_data(res.json())
    except ValueError:
        return billing, invoice_id

    if isinstance(payload, dict):
        consultation_fee = payload.get("consultation_fee", 0)
        medicine_fee = payload.get("medicine_fee", 0)
        amount = payload.get("amount", consultation_fee + medicine_fee)

        try:
            billing["consultation_fee"] = float(consultation_fee)
        except (TypeError, ValueError):
            billing["consultation_fee"] = 0.0

        try:
            billing["medicine_fee"] = float(medicine_fee)
        except (TypeError, ValueError):
            billing["medicine_fee"] = 0.0

        try:
            billing["amount"] = float(amount)
        except (TypeError, ValueError):
            billing["amount"] = 0.0

        billing["payment_status"] = payload.get("payment_status", "Pending")
        invoice_id = payload.get("invoice_id")

    return billing, invoice_id


async def _extract_delivery_status_async(client, appointment_id, patient_id, invoice_id):
    # Required endpoint from spec.
    res = await _safe_get_async(
        client,
        f"{DELIVERY_URL}/deliveries/{patient_id}",
        params={"appointment_id": appointment_id}
    )

    # Optional route mentioned in spec.
    if res and res.status_code == 404 and invoice_id:
        res = await _safe_get_async(client, f"{DELIVERY_URL}/deliveries/invoice/{invoice_id}")

    # Fallback to current atomic delivery implementation.
    if res and res.status_code == 404:
        res = await _safe_get_async(client, f"{DELIVERY_URL}/deliveries/{patient_id}", params={"appointment_id": appointment_id})

    if not res or res.status_code == 404 or res.status_code >= 400:
        return None

    try:
        payload = _extract_data(res.json())
    except ValueError:
        return None

    if isinstance(payload, list) and payload:
        row = payload[0]
    elif isinstance(payload, dict):
        row = payload
    else:
        return None

    if isinstance(row, dict):
        return {
            "id": row.get("delivery_id"),
            "tracking_number": row.get("tracking_number"),
            "address": row.get("patient_address"),
            "status": row.get("delivery_status"),
        }

    return None

semaphore = asyncio.Semaphore(10)
async def _build_bundle(client, appt, patient_id, doctor_cache):
    async with semaphore:
        raw_id = appt.get("appointment_id", appt.get("id"))
        if raw_id is None:
            return None

        try:
            appointment_id = int(raw_id)
        except (TypeError, ValueError):
            return None
        doctor_id = appt.get("doctor_id")

        prescription_task = _extract_prescription_block_async(client, appointment_id)
        invoice_task = _extract_invoice_block_async(client, appointment_id)
        doctor_task = _extract_doctor_async(client, doctor_id, doctor_cache)

        (mc_block, prescriptions), (invoice_data, invoice_id), doctor_data = await asyncio.gather(
            prescription_task,
            invoice_task,
            doctor_task,
        )

        delivery_status = await _extract_delivery_status_async(
            client, appointment_id, patient_id, invoice_id
        )

        doctor_obj = ConsultDoctor(
            id=doctor_data["id"] if doctor_data else None,
            name=doctor_data["name"] if doctor_data else "Unknown",
            specialty=doctor_data["specialty"] if doctor_data else "Unknown",
        )

        appointment_obj = ConsultAppointment(
            id=appointment_id,
            consult_id=f"CONSULT-{str(appointment_id).zfill(3)}",
            patient_id=patient_id,
            doctor=doctor_obj,
            datetime=appt.get("date") or appt.get("slot_datetime"),
            notes=appt.get("clinical_notes") or "No doctor notes recorded for this consultation.",
            status=_friendly_status(appt.get("status")),
        )

        prescription_obj = (
            Prescription(
                id=appointment_id,
                items=[
                    PrescriptionItem(
                        id=i + 1,
                        medicine_code=item.get("medicine_code"),
                        medicine_name=item["medicine_name"],
                        dosage=item.get("dosage"),
                        unit=item.get("unit"),
                        instructions=item.get("instructions"),
                        quantity=item["quantity"],
                        unit_price=item.get("unit_price"),
                        line_total=item.get("line_total"),
                    )
                    for i, item in enumerate(prescriptions)
                ],
            )
            if prescriptions
            else None
        )

        invoice_obj = None
        if invoice_id:
            invoice_obj = Invoice(
                id=invoice_id,
                consultation_fee=invoice_data["consultation_fee"],
                medicine_fee=invoice_data["medicine_fee"],
                total=invoice_data["amount"],
                status=invoice_data["payment_status"],
                currency="SGD"
            )

        delivery_obj = None
        if delivery_status:
            delivery_obj = Delivery(
                id=str(delivery_status.get("id")) if delivery_status.get("id") else None,
                tracking_number=delivery_status.get("tracking_number"),
                address=delivery_status.get("address"),
                status=delivery_status.get("status"),
                estimated_date=None
            )

        return ConsultationData(
            appointment=appointment_obj,
            prescription=prescription_obj,
            invoice=invoice_obj,
            delivery=delivery_obj,
        )


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
#         billing, invoice_id = _extract_invoice_block_async(appointment_id)
#         billing["delivery_status"] = _extract_delivery_status_async(appointment_id, appt_patient_id, invoice_id)
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


# GraphQL Types
@strawberry.type
class ConsultDoctor:
    id: Optional[int]
    name: Optional[str]
    specialty: Optional[str]

@strawberry.type
class ConsultAppointment:
    id: int
    consult_id: str
    patient_id: int
    doctor: ConsultDoctor
    datetime: Optional[str]
    notes: Optional[str]
    status: str

@strawberry.type
class PrescriptionItem:
    id: int
    medicine_name: str
    medicine_code: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    quantity: int
    unit: Optional[str] = None
    instructions: Optional[str] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None

@strawberry.type
class Prescription:
    id: int
    items: List[PrescriptionItem]

@strawberry.type
class Invoice:
    id: Optional[str]
    consultation_fee: float
    medicine_fee: float
    total: float
    status: str
    currency: Optional[str] = "SGD"

@strawberry.type
class Delivery:
    id: Optional[str]
    tracking_number: Optional[str]
    address: Optional[str]
    status: Optional[str]
    estimated_date: Optional[str]

@strawberry.type
class ConsultationData:
    appointment: ConsultAppointment
    prescription: Optional[Prescription]
    invoice: Optional[Invoice]
    delivery: Optional[Delivery]

@strawberry.type
class Query:

    @strawberry.field
    async def consultationHistory(self, patientId: int) -> List[ConsultationData]:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            # Fetch appointments for patient
            res = await _safe_get_async(client, f"{APPOINTMENT_URL}/appointments/patient/{patientId}")
            if not res or res.status_code >= 400:
                return []

            try:
                appointments_data = _extract_data(res.json())
            except ValueError:
                return []

            appointments_list = appointments_data if isinstance(appointments_data, list) else [appointments_data]

            # Doctor cache to prevent repeated calls
            doctor_cache = {}

            # Build bundles concurrently with a semaphore
            tasks = [
                _build_bundle(client, appt, patientId, doctor_cache)
                for appt in appointments_list
            ]
            bundles = await asyncio.gather(*tasks)

            # Filter out any None results
            valid_bundles = [b for b in bundles if b is not None]
            valid_bundles.sort(key=lambda b: b.appointment.datetime or "", reverse=True)

            return valid_bundles



schema = strawberry.Schema(query=Query)
graphql_app = GraphQL(schema)
app = Starlette(routes=[
    Route("/api/graphql", graphql_app)
])
# app.add_url_rule(
#     "/graphql",
#     view_func=GraphQLView.as_view("graphql_view", schema=schema),
# )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5013)
