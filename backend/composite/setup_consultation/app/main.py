from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flasgger import Swagger
from werkzeug.exceptions import HTTPException

from app.error_publisher import publish_error as _publish_error
from app import upstream
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
    if status_code >= 500:
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


@app.route("/next-patient", methods=["POST"])
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
            no_show_appointment_id:
              type: integer
              example: 42
              description: Optional — ID of the appointment to mark as no-show before dequeuing the next patient
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

    no_show_id = data.get("no_show_appointment_id") if data else None
    if no_show_id is not None:
        upstream.handle_no_show(no_show_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_dequeue = executor.submit(upstream.dequeue_patient)
        f_zoom = executor.submit(upstream.create_zoom_meeting)
        patient_id = f_dequeue.result()
        join_url = f_zoom.result()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_appt = executor.submit(upstream.create_appointment, patient_id, doctor_id, join_url)
        f_patient = executor.submit(upstream.get_patient_details, patient_id)
        appointment_id = f_appt.result()
        patient_data = f_patient.result()

    upstream.notify_head_of_queue(patient_data["email"], join_url)

    return jsonify({
        "code": 200,
        "patient": patient_data,
        "appointment_id": appointment_id,
        "meet_link": join_url,
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5012, debug=True)
