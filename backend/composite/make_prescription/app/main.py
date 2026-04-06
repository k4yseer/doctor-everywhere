from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
import requests
import base64
import os
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST

from error_publisher import publish_error as _publish_error
import notification_publisher

app = Flask(__name__)
CORS(app)
Swagger(app)  # Swagger UI at /apidocs

SERVICE_NAME = "make_prescription"
SERVICE_UP = Gauge("service_up", "1 if service is up, 0 otherwise", ["service_name"])

def error_response(status_code, message, error_code, payload=None):
    if status_code >= 400:
        _publish_error(
            source_service=SERVICE_NAME,
            error_code=error_code,
            error_message=message,
            payload=payload,
        )
    return jsonify({"code": status_code, "message": message}), status_code


# ─── Service URLs ──────────────────────────────────────────────────────────────
PATIENT_SERVICE_URL    = os.environ.get("PATIENT_SERVICE_URL",    "http://patient-service:5003")
INVENTORY_SERVICE_URL  = os.environ.get("INVENTORY_SERVICE_URL",  "http://inventory-service:5009")
APPOINTMENT_SERVICE_URL = os.environ.get("APPOINTMENT_SERVICE_URL", "http://appointment-service:5002")
INVOICE_SERVICE_URL    = os.environ.get("INVOICE_SERVICE_URL",    "http://invoice-service:5008")
PRESCRIPTION_SERVICE_URL = os.environ.get(
    "PRESCRIPTION_SERVICE_URL", 
    "https://personal-pehihv0m.outsystemscloud.com/ESDPrescriptionService/rest/PrescriptionAPI")

CONSULTATION_FEE = float(os.environ.get("CONSULTATION_FEE", 50.0))
CURRENCY = os.environ.get("CURRENCY", "SGD")

# ─── Main Endpoint ─────────────────────────────────────────────────────────────
@app.route("/api/make-prescription", methods=["POST"])
def make_prescription():
    """
    Composite: orchestrate allergy check, inventory reservation, and prescription creation.
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
            medicines:
              type: array
              items:
                type: object
                properties:
                  medicine_code:
                    type: string
                  medicine_name:
                    type: string
                  dosage_instructions:
                    type: string
                  dispense_quantity:
                    type: integer
            mc_start_date:
              type: string
              format: date
            mc_duration_days:
              type: integer
            consultation_notes:
              type: string
    responses:
      201:
        description: Prescription created successfully
      400:
        description: Allergy conflict or insufficient stock
      500:
        description: Internal service error
    """
    data = request.get_json()

    appointment_id      = data.get("appointment_id")
    patient_id          = data.get("patient_id")
    medicines           = data.get("medicines", [])
    mc_start_date       = data.get("mc_start_date")
    mc_duration_days    = data.get("mc_duration_days")
    mc_diagnosis        = data.get("mc_diagnosis", "")
    consultation_notes  = data.get("consultation_notes", "")
    consultation_fee    = CONSULTATION_FEE
    medicine_fee        = 0.0
    currency            = CURRENCY

    if not all([appointment_id, patient_id]):
        return error_response(
            400,
            "Missing required fields",
            "MAKE-PRESCRIPTION-400-MISSING_FIELDS",
            {"appointment_id": appointment_id, "patient_id": patient_id},
        )

    try:
        appointment_id = int(appointment_id)
        if appointment_id <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return error_response(
            400,
            "appointment_id must be a positive integer",
            "MAKE-PRESCRIPTION-400-INVALID_APPOINTMENT_ID",
            {"appointment_id": appointment_id},
        )

    try:
        patient_id = int(patient_id)
        if patient_id <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return error_response(
            400,
            "patient_id must be a positive integer",
            "MAKE-PRESCRIPTION-400-INVALID_PATIENT_ID",
            {"patient_id": patient_id},
        )

    # ── Step 3: Check patient allergies ────────────────────────────────────────
    try:
        prescription_names = [
            str(m.get("medicine_name", "")).strip()
            for m in medicines
            if str(m.get("medicine_code", "")).upper() != "MC" and str(m.get("medicine_name", "")).strip()
        ]

        allergy_resp = requests.post(
            f"{PATIENT_SERVICE_URL}/patient/check-allergies",
            json={
                "patient_id": patient_id,
                "prescription": prescription_names,
            },
            timeout=5
        )

        if allergy_resp.status_code == 200:
            allergy_data = allergy_resp.json().get("data", {})
            if allergy_data.get("check") == "FAILED":
                allergic_drugs = allergy_data.get("allergic_drugs") or []
                if allergic_drugs:
                    return error_response(
                        400,
                        f"Patient is allergic to {', '.join(map(str, allergic_drugs))}",
                        "MAKE-PRESCRIPTION-400-ALLERGY_CONFLICT",
                        {"allergic_drugs": allergic_drugs},
                    )
                return error_response(
                    400,
                    "Patient has an allergy conflict with prescribed medicine",
                    "MAKE-PRESCRIPTION-400-ALLERGY_CONFLICT",
                )
        elif allergy_resp.status_code == 404:
            return error_response(
                404,
                "Patient not found",
                "MAKE-PRESCRIPTION-404-PATIENT_NOT_FOUND",
                {"patient_id": patient_id},
            )
        else:
            raise Exception(f"Patient service returned {allergy_resp.status_code}")

    except Exception as e:
        _publish_error("patient_service", "PATIENT-500", str(e), data)
        return error_response(
            500,
            "Failed to verify patient allergies",
            "MAKE-PRESCRIPTION-500-PATIENT_CHECK_FAILED",
            {"error": str(e)},
        )

    # ── Step 5: Check and reserve inventory for all medicines ──────────────────
    reservations = []
    for medicine in medicines:
        medicine_code = medicine.get("medicine_code")
        dispense_quantity = medicine.get("dispense_quantity", 0)
        try:
            dispense_quantity = int(dispense_quantity)
            if dispense_quantity <= 0:
                raise ValueError()
        except (TypeError, ValueError):
            return error_response(
                400,
                "dispense_quantity must be a positive integer",
                "MAKE-PRESCRIPTION-400-INVALID_QUANTITY",
                {"medicine_code": medicine_code, "dispense_quantity": medicine.get("dispense_quantity")},
            )
        if medicine_code and medicine_code != "MC":
            try:
                stock_resp = requests.get(
                    f"{INVENTORY_SERVICE_URL}/inventory/{medicine_code}",
                    timeout=5
                )
                if stock_resp.status_code != 200:
                    stock = {}
                else:
                    stock = stock_resp.json().get("data", {})
                if stock and stock.get("stock_available", 0) < dispense_quantity:
                    return error_response(
                        400,
                        f"Insufficient stock for {medicine_code}",
                        "MAKE-PRESCRIPTION-400-INSUFFICIENT_STOCK",
                        {"medicine_code": medicine_code, "available": stock.get("stock_available", 0), "requested": dispense_quantity},
                    )
                unit_price = stock.get("unit_price", 0.0)
                try:
                    unit_price = float(unit_price)
                except (TypeError, ValueError):
                    unit_price = 0.0

                line_total = round(unit_price * dispense_quantity, 2)
                medicine["unit_price"] = unit_price
                medicine["total_price"] = line_total
                medicine_fee += line_total

                reserve_resp = requests.post(
                    f"{INVENTORY_SERVICE_URL}/inventory/reservations/",
                    json={
                        "medicine_code": medicine_code,
                        "appointment_id": int(appointment_id),
                        "amount": int(dispense_quantity)
                    },
                    timeout=5
                )
                if reserve_resp.status_code not in (200, 201):
                    raise Exception(f"Reservation failed for {medicine_code}: {reserve_resp.text}")

                reservations.append(reserve_resp.json().get("data", {}))

            except Exception as e:
                _publish_error("inventory_service", "INVENTORY-500", str(e), data)
                return jsonify({"code": 500, "message": "Failed to reserve inventory"}), 500

    # ── Step 7: Create prescription records via OutSystems ─────────────────────
    out_prescriptions = []
    
    # Send empty prescription just for MC if no medicines exist
    if not medicines and (mc_start_date and mc_duration_days):
        try:
            prescription_resp = requests.post(
                f"{PRESCRIPTION_SERVICE_URL}/CreatePrescription",
                json={
                    "appointment_id":      appointment_id,
                    "patient_id":          patient_id,
                    "medicine_code":       "MC",
                    "medicine_name":       "MC",
                    "dosage_instructions": "-",
                    "dispense_quantity":   0,
                    "total_price":         0.0,
                    "mc_start_date":       mc_start_date,
                    "mc_duration_days":    int(mc_duration_days) if mc_duration_days else 0,
                },
                timeout=5
            )
            if prescription_resp.status_code not in (200, 201):
                raise Exception(f"Prescription service returned {prescription_resp.status_code}: {prescription_resp.text}")

            prescription = prescription_resp.json()
            prescription_id = prescription if isinstance(prescription, int) else prescription.get("data", {}).get("prescription_id")
            if prescription_id:
                out_prescriptions.append({"prescription_id": prescription_id})
        except Exception as e:
            _publish_error("prescription_service", "PRESCRIPTION-500", str(e), data)
            return jsonify({"code": 500, "message": "Failed to create MC prescription record"}), 500

    else:
        for i, medicine in enumerate(medicines):
            try:
                medicine_code = medicine.get("medicine_code") or ""
                
                prescription_resp = requests.post(
                    f"{PRESCRIPTION_SERVICE_URL}/CreatePrescription",
                    json={
                        "appointment_id":      appointment_id,
                        "patient_id":          patient_id,
                        "medicine_code":       medicine_code,
                        "medicine_name":       str(medicine.get("medicine_name") or ""),
                        "dosage_instructions": medicine.get("dosage_instructions") or "",
                        "dispense_quantity":   int(medicine.get("dispense_quantity") or 0),
                        "total_price":         float(medicine.get("total_price") or 0.0),
                        "mc_start_date":       mc_start_date if mc_start_date else "1900-01-01",
                        "mc_duration_days":    int(mc_duration_days) if mc_duration_days else 0,
                    },
                    timeout=5
                )
                if prescription_resp.status_code not in (200, 201):
                    raise Exception(f"Prescription service returned {prescription_resp.status_code}: {prescription_resp.text}")

                prescription = prescription_resp.json()
                prescription_id = prescription if isinstance(prescription, int) else prescription.get("data", {}).get("prescription_id")
                if prescription_id:
                    out_prescriptions.append({"prescription_id": prescription_id})
                    
            except Exception as e:
                _publish_error("prescription_service", "PRESCRIPTION-500", str(e), data)
                return jsonify({"code": 500, "message": f"Failed to create prescription record for {medicine_code}"}), 500

    # ── Step 8: Update Appointment Status and Notes ───────────────────────────────
    try:
        payload = {"status": "PENDING_PAYMENT"}
        if consultation_notes:
            payload["clinical_notes"] = consultation_notes

        print(f"[MAKE PRESCRIPTION] Updating appointment {appointment_id} to PENDING_PAYMENT")
        appt_resp = requests.put(
            f"{APPOINTMENT_SERVICE_URL}/appointments/{appointment_id}/status",
            json=payload,
            timeout=5
        )
        print(f"[MAKE PRESCRIPTION] Appointment update response: {appt_resp.status_code} {appt_resp.text}")
        if appt_resp.status_code != 200:
            raise Exception(f"Appointment service returned {appt_resp.status_code}")
    except Exception as e:
        _publish_error("appointment_service", "APPOINTMENT-500", str(e), data)
        print(f"[MAKE PRESCRIPTION] Failed to update appointment status: {e}")

    # ── Step 10: Publish PRESCRIPTION_MADE for Resend notification ─────────────
    if mc_start_date and mc_duration_days:
        try:
            from datetime import date, timedelta
            patient_resp = requests.get(f"{PATIENT_SERVICE_URL}/patient/{patient_id}/details", timeout=5)
            patient_data = patient_resp.json().get("data", {})
            patient_email = patient_data.get("email", "")
            patient_name  = patient_data.get("patient_name", f"Patient {patient_id}")

            start = date.fromisoformat(mc_start_date)
            end   = start + timedelta(days=int(mc_duration_days) - 1)
            issued_on = date.today().strftime("%d %B %Y")
            start_fmt = start.strftime("%d %B %Y")
            end_fmt   = end.strftime("%d %B %Y")
            diagnosis = mc_diagnosis.strip() if mc_diagnosis else "As certified by attending physician"

            from fpdf import FPDF

            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 16)
            pdf.cell(200, 10, txt="MEDICAL CERTIFICATE", ln=True, align="C")
            pdf.set_font("Arial", "", 11)
            pdf.cell(200, 8, txt="Doctor Everywhere Telehealth Services", ln=True, align="C")
            pdf.ln(4)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(6)

            pdf.set_font("Arial", "", 11)
            pdf.cell(200, 8, txt=f"Date Issued: {issued_on}    |    Ref: MC-{appointment_id}", ln=True)
            pdf.ln(4)

            pdf.set_font("Arial", "B", 11)
            pdf.cell(60, 8, txt="Patient Name:", ln=False)
            pdf.set_font("Arial", "", 11)
            pdf.cell(0, 8, txt=patient_name, ln=True)

            pdf.set_font("Arial", "B", 11)
            pdf.cell(60, 8, txt="Patient ID:", ln=False)
            pdf.set_font("Arial", "", 11)
            pdf.cell(0, 8, txt=str(patient_id), ln=True)
            pdf.ln(4)

            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(6)

            pdf.set_font("Arial", "", 11)
            pdf.multi_cell(0, 8, txt=(
                f"This is to certify that the above-named patient was examined on {issued_on} "
                f"and is medically unfit for work or school duties for the period stated below."
            ))
            pdf.ln(4)

            pdf.set_font("Arial", "B", 11)
            pdf.cell(60, 8, txt="Diagnosis:", ln=False)
            pdf.set_font("Arial", "", 11)
            pdf.multi_cell(0, 8, txt=diagnosis)
            pdf.ln(2)

            pdf.set_font("Arial", "B", 11)
            pdf.cell(60, 8, txt="Leave From:", ln=False)
            pdf.set_font("Arial", "", 11)
            pdf.cell(0, 8, txt=start_fmt, ln=True)

            pdf.set_font("Arial", "B", 11)
            pdf.cell(60, 8, txt="Leave To:", ln=False)
            pdf.set_font("Arial", "", 11)
            pdf.cell(0, 8, txt=end_fmt, ln=True)

            pdf.set_font("Arial", "B", 11)
            pdf.cell(60, 8, txt="Duration:", ln=False)
            pdf.set_font("Arial", "", 11)
            pdf.cell(0, 8, txt=f"{mc_duration_days} day(s)", ln=True)
            pdf.ln(10)

            pdf.line(10, pdf.get_y(), 80, pdf.get_y())
            pdf.ln(4)
            pdf.set_font("Arial", "", 11)
            pdf.cell(200, 8, txt="Attending Physician", ln=True)
            pdf.set_font("Arial", "I", 10)
            pdf.cell(200, 8, txt="Doctor Everywhere Telehealth", ln=True)

            pdf_bytes = pdf.output()
            mc_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

            notification_publisher.publish_notification("send-mc", {
                "email": patient_email,
                "appointment_id": appointment_id,
                "filename": f"MC_{appointment_id}.pdf",
                "file_content": mc_base64,
            })
        except Exception as e:
            _publish_error("notification_service", "NOTIF-500", str(e), data)
            print(f"[MAKE PRESCRIPTION] Failed to publish MC notification: {e}")

    try:
        invoice_resp = requests.post(
            f"{INVOICE_SERVICE_URL}/invoices/{appointment_id}",
            json={
                "patient_id": patient_id,
                "consultation_fee": consultation_fee,
                "medicine_fee": medicine_fee,
                "amount": consultation_fee + medicine_fee,
                "currency": currency,
                "payment_status": "PENDING",
            },
            timeout=10,
        )
        if invoice_resp.status_code == 409:
            # Invoice already exists → GET it instead
            invoice_resp = requests.get(f"{INVOICE_SERVICE_URL}/invoices/{appointment_id}")
            invoice = invoice_resp.json().get("data", {})
        elif invoice_resp.status_code not in (200, 201):
            raise Exception(f"Invoice service returned {invoice_resp.status_code}: {invoice_resp.text}")
        else:
            invoice = invoice_resp.json().get("data", {})
    except Exception as e:
        _publish_error("invoice_service", "INVOICE-500", str(e), data)
        return jsonify({"code": 500, "message": "Failed to create invoice"}), 500

    return jsonify({
        "code": 201,
        "message": "Prescription created successfully",
        "data": {
            "prescriptions": out_prescriptions,
            "reservations":  reservations,
            "invoice": invoice,
        }
    }), 201


# ─── Entrypoint ────────────────────────────────────────────────────────────────
@app.route("/metrics")
def metrics():
    SERVICE_UP.labels(service_name=SERVICE_NAME).set(1)
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5015, debug=False)