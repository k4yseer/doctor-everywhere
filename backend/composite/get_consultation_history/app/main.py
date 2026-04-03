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
    if status_code >= 500:
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
        return await client.get(url, params=params)
    except httpx.RequestError:
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

    # Try OutSystems for MC data
    res = await _safe_get_async(client, f"{PRESCRIPTION_URL}/GetPrescription", params={"AppointmentId": appointment_id})
    if res and res.status_code < 400:
        try:
            payload = _extract_data(res.json())
        except ValueError:
            payload = None

        if payload:
            rows = payload if isinstance(payload, list) else [payload]
            for row in rows:
                if not isinstance(row, dict):
                    continue
                has_mc = row.get("has_mc") or row.get("hasMC")
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

    # Use inventory reservations as the source for medicine items
    res = await _safe_get_async(client, f"{INVENTORY_URL}/inventory/reservations/appointment/{appointment_id}")
    if res and res.status_code < 400:
        try:
            reservations = res.json()
            if not isinstance(reservations, list):
                reservations = []
        except ValueError:
            reservations = []

        for rv in reservations:
            if not isinstance(rv, dict):
                continue
            code = rv.get("medicine_code", "")
            qty = rv.get("amount", 0)
            name = code
            med_res = await _safe_get_async(client, f"{INVENTORY_URL}/inventory/{code}")
            if med_res and med_res.status_code < 400:
                try:
                    med_data = _extract_data(med_res.json())
                    if isinstance(med_data, dict):
                        name = med_data.get("medicine_name", code)
                except ValueError:
                    pass
            prescriptions.append({"drug_name": name, "quantity": qty})

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
            notes=appt.get("clinical_notes"),
            status=_friendly_status(appt.get("status")),
        )

        prescription_obj = (
            Prescription(
                id=appointment_id,
                items=[
                    PrescriptionItem(
                        id=i + 1,
                        name=item["drug_name"],
                        quantity=item["quantity"],
                    )
                    for i, item in enumerate(prescriptions)
                ],
            )
            if prescriptions
            else None
        )

        invoice_obj = None
        if invoice_id:
            invoice_obj = {
                "id": invoice_id,
                "consultation_fee": invoice_data["consultation_fee"],
                "medicine_fee": invoice_data["medicine_fee"],
                "total": invoice_data["amount"],
                "status": invoice_data["payment_status"],
            }

        return ConsultationData(
            appointment=appointment_obj,
            prescription=prescription_obj,
            invoice=invoice_obj,
            delivery=delivery_status,
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
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    quantity: int
    unit: Optional[str] = None
    instructions: Optional[str] = None

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
    prescription: Prescription
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

            # Convert to GraphQL types
            graphql_results = []
            for b in valid_bundles:
                appointment_obj = ConsultAppointment(
                    id=b.appointment.id,
                    consult_id=b.appointment.consult_id,
                    patient_id=b.appointment.patient_id,
                    doctor=ConsultDoctor(
                        id=b.appointment.doctor.id,
                        name=b.appointment.doctor.name,
                        specialty=b.appointment.doctor.specialty
                    ),
                    datetime=b.appointment.datetime,
                    notes=b.appointment.notes,
                    status=b.appointment.status
                )

                prescription_items = [
                    PrescriptionItem(
                        id=item.id,
                        name=item.name,
                        quantity=item.quantity,
                        dosage=getattr(item, "dosage", None),
                        frequency=getattr(item, "frequency", None),
                        duration=getattr(item, "duration", None),
                        unit=getattr(item, "unit", None),
                        instructions=getattr(item, "instructions", None),
                    )
                    for item in (b.prescription.items if b.prescription else [])
                ]

                prescription_obj = Prescription(
                    id=b.prescription.id if b.prescription else b.appointment.id,
                    items=prescription_items
                )

                invoice_obj = None
                if b.invoice:
                    invoice_obj = Invoice(
                        id=b.invoice["id"],
                        consultation_fee=b.invoice["consultation_fee"],
                        medicine_fee=b.invoice["medicine_fee"],
                        total=b.invoice["total"],
                        status=b.invoice["status"],
                        currency="SGD"
                    )

                delivery_obj = None
                if b.delivery:
                    delivery_obj = Delivery(
                        id=b.delivery.get("id"),
                        tracking_number=b.delivery.get("tracking_number"),
                        address=b.delivery.get("address"),
                        status=b.delivery.get("status"),
                        estimated_date=None
                    )

                graphql_results.append(
                    ConsultationData(
                        appointment=appointment_obj,
                        prescription=prescription_obj,
                        invoice=invoice_obj,
                        delivery=delivery_obj
                    )
                )

            return graphql_results



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
