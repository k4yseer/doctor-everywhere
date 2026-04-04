from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flasgger import Swagger
from werkzeug.exceptions import HTTPException

from app.error_publisher import publish_error as _publish_error
from app import upstream, notification_publisher
from app.upstream import UpstreamError

SERVICE_NAME = "consultation-setup"

app = Flask(__name__)
swagger = Swagger(app, template={
    "info": {
        "title": "Setup Consultation Composite Service API",
        "version": "1.0.0",
        "description": (
            "Orchestrates dequeue, teleconferencing, appointment creation, "
            "patient fetch, and notification for a doctor's next patient"
        )
    }
})


def error_response(status_code, message, error_code, payload=None):
    if status_code >= 400:
        _publish_error(source_service=SERVICE_NAME, error_code=error_code, error_message=message, payload=payload)
    return jsonify({"code": status_code, "message": message}), status_code


@app.errorhandler(UpstreamError)
def handle_upstream_error(err):
    return error_response(err.status_code, err.message, err.error_code)


@app.errorhandler(Exception)
def handle_unexpected_error(err):
    if isinstance(err, HTTPException):
        return error_response(
            err.code or 500,
            err.description,
            f"CONSULT-{err.code or 500}-HTTP",
            {"path": request.path, "method": request.method},
        )
    return error_response(
        500,
        "Internal server error",
        "CONSULT-500-UNHANDLED",
        {"path": request.path, "method": request.method, "error": str(err)},
    )


@app.route("/api/setup-consultation/no-show", methods=["POST"])
def no_show():
    """
    Mark an appointment as no-show and notify the patient.
    ---
    tags:
      - Consultation Setup
    summary: Mark appointment as no-show
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - appointment_id
          properties:
            appointment_id:
              type: integer
              example: 42
    responses:
      200:
        description: Appointment marked as no-show and patient notified
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            message:
              type: string
              example: "Appointment 42 marked as no-show"
      400:
        description: Missing required field
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "appointment_id is required"
      503:
        description: Upstream service unavailable
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 503
            message:
              type: string
              example: "Appointment service unreachable"
    """
    data = request.get_json()
    appointment_id = data.get("appointment_id") if data else None

    if not appointment_id:
        return error_response(400, "appointment_id is required", "CONSULT-400-MISSING_FIELDS")

    upstream.handle_no_show(appointment_id)

    return jsonify({"code": 200, "message": f"Appointment {appointment_id} marked as no-show"}), 200


@app.route("/api/setup-consultation/next-patient", methods=["POST"])
def next_patient():
    """
    Trigger full consultation setup for the next patient in queue.
    ---
    tags:
      - Consultation Setup
    summary: Dequeue next patient and set up consultation
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - doctor_id
          properties:
            doctor_id:
              type: integer
              example: 1
    responses:
      200:
        description: Consultation setup successful
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            patient:
              type: object
            appointment_id:
              type: integer
              example: 42
            meet_link:
              type: string
              example: "https://zoom.us/j/123456789"
            start_url:
              type: string
              example: "https://zoom.us/s/123456789?zak=abc"
      400:
        description: Missing required field
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 400
            message:
              type: string
              example: "doctor_id is required"
      404:
        description: Queue is empty
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 404
            message:
              type: string
              example: "Queue is empty"
      503:
        description: Upstream service unavailable
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 503
            message:
              type: string
              example: "Queue service unreachable"
    """
    data = request.get_json()
    doctor_id = data.get("doctor_id") if data else None

    if not doctor_id:
        return error_response(400, "doctor_id is required", "CONSULT-400-MISSING_FIELDS")

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_dequeue = executor.submit(upstream.dequeue_patient)
        f_zoom = executor.submit(upstream.create_zoom_meeting)
        patient_id = f_dequeue.result()
        zoom_urls = f_zoom.result()
        join_url = zoom_urls["join_url"]
        start_url = zoom_urls["start_url"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_appt = executor.submit(upstream.create_appointment, patient_id, doctor_id, join_url, start_url)
        f_patient = executor.submit(upstream.get_patient_details, patient_id)
        appointment_id = f_appt.result()
        patient_data = f_patient.result()

    upstream.notify_head_of_queue(patient_data["email"], join_url)

    return jsonify({
        "code": 200,
        "patient": patient_data,
        "appointment_id": appointment_id,
        "meet_link": join_url,
        "start_url": start_url,
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5012, debug=True)
