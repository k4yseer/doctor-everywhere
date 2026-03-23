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
PATIENT_SERVICE_URL    = os.environ.get("PATIENT_SERVICE_URL",    "http://patient-service:5003")
INVENTORY_SERVICE_URL  = os.environ.get("INVENTORY_SERVICE_URL",  "http://inventory-service:5009")
PRESCRIPTION_SERVICE_URL = os.environ.get(
    "PRESCRIPTION_SERVICE_URL", 
    "https://personal-pehihv0m.outsystemscloud.com/ESDPrescriptionService/rest/PrescriptionAP")

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
        print(f"[MAKE PRESCRIPTION] Published to '{routing_key}'")
    except Exception as e:
        print(f"[MAKE PRESCRIPTION] AMQP publish failed: {e}")


# ─── Main Endpoint ─────────────────────────────────────────────────────────────
@app.route("/make-prescription", methods=["POST"])
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
              type: string
            patient_id:
              type: string
            drug_code:
              type: string
            medication_name:
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
    drug_code           = data.get("drug_code")
    medication_name     = data.get("medication_name")
    dosage_instructions = data.get("dosage_instructions")
    dispense_quantity   = data.get("dispense_quantity")
    mc_start_date       = data.get("mc_start_date")
    mc_duration_days    = data.get("mc_duration_days")

    if not all([appointment_id, patient_id, drug_code, medication_name, dispense_quantity]):
        return jsonify({"code": 400, "message": "Missing required fields"}), 400

    # ── Step 3: Check patient allergies ────────────────────────────────────────
    try:
        allergy_resp = requests.get(
            f"{PATIENT_SERVICE_URL}/patients/{patient_id}/allergies",
            timeout=5
        )
        if allergy_resp.status_code == 200:
            allergies = allergy_resp.json().get("data", [])
            allergy_list = [a.get("allergy", "").lower() for a in allergies]
            if medication_name.lower() in allergy_list:
                return jsonify({
                    "code": 400,
                    "message": f"Patient is allergic to {medication_name}"
                }), 400
        elif allergy_resp.status_code != 404:
            # 404 just means no allergies on record — that's fine
            raise Exception(f"Patient service returned {allergy_resp.status_code}")

    except Exception as e:
        _publish_error("patient_service", "PATIENT-500", str(e), data)
        return jsonify({"code": 500, "message": "Failed to verify patient allergies"}), 500

    # ── Step 5: Check and reserve inventory ────────────────────────────────────
    try:
        stock_resp = requests.get(
            f"{INVENTORY_SERVICE_URL}/inventory/{drug_code}",
            timeout=5
        )
        if stock_resp.status_code != 200:
            return jsonify({"code": 400, "message": f"Drug {drug_code} not found in inventory"}), 400

        stock = stock_resp.json().get("data", {})
        if stock.get("stock_available", 0) < dispense_quantity:
            return jsonify({"code": 400, "message": "Insufficient stock"}), 400

        reserve_resp = requests.post(
            f"{INVENTORY_SERVICE_URL}/inventory/reservations/",
            json={
                "drug_code": drug_code,
                "patient_id": patient_id,
                "amount": dispense_quantity
            },
            timeout=5
        )
        if reserve_resp.status_code not in (200, 201):
            raise Exception(f"Reservation failed: {reserve_resp.text}")

        reservation = reserve_resp.json().get("data", {})

    except Exception as e:
        _publish_error("inventory_service", "INVENTORY-500", str(e), data)
        return jsonify({"code": 500, "message": "Failed to reserve inventory"}), 500

    # ── Step 7: Create prescription record ─────────────────────────────────────
    try:
        prescription_resp = requests.post(
            f"{PRESCRIPTION_SERVICE_URL}/prescriptions/",
            json={
                "appointment_id":      appointment_id,
                "patient_id":          patient_id,
                "medication_name":     medication_name,
                "dosage_instructions": dosage_instructions,
                "dispense_quantity":   dispense_quantity,
                "mc_start_date":       mc_start_date,
                "mc_duration_days":    mc_duration_days,
            },
            timeout=5
        )
        if prescription_resp.status_code not in (200, 201):
            raise Exception(f"Prescription service returned {prescription_resp.status_code}")

        prescription = prescription_resp.json().get("data", {})

    except Exception as e:
        _publish_error("prescription_service", "PRESCRIPTION-500", str(e), data)
        return jsonify({"code": 500, "message": "Failed to create prescription record"}), 500

    # ── Step 10: Publish PRESCRIPTION_MADE for Twilio notification ─────────────
    publish_message(
        routing_key="prescription.made",
        message={
            "patient_id":      patient_id,
            "appointment_id":  appointment_id,
            "medication_name": medication_name,
            "mc_start_date":   mc_start_date,
            "mc_duration_days": mc_duration_days,
            "prescription_id": prescription.get("prescription_id")
        }
    )

    return jsonify({
        "code": 201,
        "message": "Prescription created successfully",
        "data": {
            "prescription": prescription,
            "reservation":  reservation
        }
    }), 201


# ─── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5015, debug=False)