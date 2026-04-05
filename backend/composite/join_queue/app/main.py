import math
import os
import requests
from flask import Flask, jsonify, request
from flasgger import Swagger
from werkzeug.exceptions import HTTPException
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST

from app.error_publisher import publish_error as _publish_error

app = Flask(__name__)
swagger = Swagger(app, template={
    "info": {
        "title": "Join Queue Composite Service API",
        "version": "1.0.0",
        "description": (
            "Orchestrates doctor availability and queue entry"
        )
    }
})

DOCTOR_SERVICE_URL = os.getenv("DOCTOR_SERVICE_URL", "http://doctor-service:5001")
QUEUE_SERVICE_URL = os.getenv("QUEUE_SERVICE_URL", "http://queue-service:5011")
SERVICE_NAME = "join-queue"
SERVICE_UP = Gauge("service_up", "1 if service is up, 0 otherwise", ["service_name"])


class UpstreamError(Exception):
    def __init__(self, status_code, message, error_code):
        self.status_code = status_code
        self.message = message
        self.error_code = error_code


def error_response(status_code, message, error_code, payload=None):
    if status_code >= 400:
        _publish_error(source_service=SERVICE_NAME, error_code=error_code, error_message=message, payload=payload)
    return jsonify({"code": status_code, "message": message}), status_code


def _forward_error(res):
    try:
        message = res.json().get("message", "Upstream service error")
    except Exception:
        message = "Upstream service error"
    raise UpstreamError(res.status_code, message, f"JOIN-QUEUE-{res.status_code}-UPSTREAM")


def _get_status_data(patient_id, available_doctors_count):
    """Fetch queue_id, position and calculate wait time for a patient already in queue."""
    try:
        pos_res = requests.get(f"{QUEUE_SERVICE_URL}/queue/position/{patient_id}")
    except requests.exceptions.RequestException:
        raise UpstreamError(503, "Queue service unreachable", "JOIN-QUEUE-503-QUEUE_UNREACHABLE")
    if not pos_res.ok:
        _forward_error(pos_res)
    body = pos_res.json()
    queue_position = body.get("queue_position")
    return {"queue_id": body.get("queue_id"), "queue_position": queue_position,
            "waiting_time": math.ceil(queue_position / available_doctors_count) * 10}


@app.errorhandler(UpstreamError)
def handle_upstream_error(err):
    return error_response(err.status_code, err.message, err.error_code)


@app.errorhandler(Exception)
def handle_unexpected_error(err):
    if isinstance(err, HTTPException):
        return error_response(
            err.code or 500,
            err.description,
            f"JOIN-QUEUE-{err.code or 500}-HTTP",
            {"path": request.path, "method": request.method},
        )
    return error_response(
        500,
        "Internal server error",
        "JOIN-QUEUE-500-UNHANDLED",
        {"path": request.path, "method": request.method, "error": str(err)},
    )


@app.route("/api/join-queue", methods=["POST"])
def join_queue():
    """
    Add a patient to the consultation queue.
    ---
    tags:
      - Join Queue
    summary: Add a patient to the consultation queue
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - patient_id
          properties:
            patient_id:
              type: integer
              example: 1
    responses:
      200:
        description: Patient already in queue — position returned by queue service
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            queue_id:
              type: integer
              example: 3
            queue_position:
              type: integer
              example: 2
            waiting_time:
              type: integer
              example: 10
            status:
              type: string
              example: "QUEUED"
      201:
        description: Patient successfully added to the queue
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 201
            queue_id:
              type: integer
              example: 4
            queue_position:
              type: integer
              example: 3
            waiting_time:
              type: integer
              description: Estimated waiting time in minutes
              example: 20
            status:
              type: string
              example: "QUEUED"
      400:
        description: Missing required field
      503:
        description: Upstream service unavailable or no doctors available
    """
    data = request.get_json()
    patient_id = data.get("patient_id") if data else None

    if not patient_id:
        return error_response(400, "patient_id is required", "JOIN-QUEUE-400-MISSING_FIELDS")

    try:
        doctors_res = requests.get(f"{DOCTOR_SERVICE_URL}/doctors", params={"status": "AVAILABLE"})
    except requests.exceptions.RequestException:
        raise UpstreamError(503, "Doctor service unreachable", "JOIN-QUEUE-503-DOCTOR_UNREACHABLE")

    if not doctors_res.ok:
        _forward_error(doctors_res)

    doctors = doctors_res.json().get("data", [])
    available_doctors_count = len(doctors)

    if available_doctors_count == 0:
        raise UpstreamError(503, "No doctors available", "JOIN-QUEUE-503-NO_DOCTORS")

    try:
        queue_res = requests.post(f"{QUEUE_SERVICE_URL}/queue", json={"patient_id": patient_id})
    except requests.exceptions.RequestException:
        raise UpstreamError(503, "Queue service unreachable", "JOIN-QUEUE-503-QUEUE_UNREACHABLE")

    if not queue_res.ok:
        _forward_error(queue_res)

    queue_body = queue_res.json()
    queue_id = queue_body.get("queue_id")
    queue_position = queue_body.get("queue_position")
    waiting_time = math.ceil(queue_position / available_doctors_count) * 10
    return jsonify({
        "code": queue_res.status_code,
        "queue_id": queue_id,
        "queue_position": queue_position,
        "waiting_time": waiting_time,
        "status": "QUEUED",
    }), queue_res.status_code


@app.route("/api/join-queue/status/<int:patient_id>", methods=["GET"])
def get_queue_status(patient_id):
    """
    Get a patient's current queue position and estimated wait time.
    ---
    tags:
      - Join Queue
    summary: Get queue status for a patient
    parameters:
      - in: path
        name: patient_id
        type: integer
        required: true
        example: 1
    responses:
      200:
        description: Queue status retrieved
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            queue_position:
              type: integer
              example: 2
            waiting_time:
              type: integer
              example: 10
            status:
              type: string
              example: "QUEUED"
      404:
        description: Patient not in queue
      503:
        description: Upstream service unavailable
    """
    try:
        doctors_res = requests.get(f"{DOCTOR_SERVICE_URL}/doctors", params={"status": "AVAILABLE"})
    except requests.exceptions.RequestException:
        raise UpstreamError(503, "Doctor service unreachable", "JOIN-QUEUE-503-DOCTOR_UNREACHABLE")

    if not doctors_res.ok:
        _forward_error(doctors_res)

    doctors = doctors_res.json().get("data", [])
    available_doctors_count = len(doctors)
    if available_doctors_count == 0:
        raise UpstreamError(503, "No doctors available", "JOIN-QUEUE-503-NO_DOCTORS")

    status_data = _get_status_data(patient_id, available_doctors_count)

    return jsonify({
        "code": 200,
        "queue_position": status_data["queue_position"],
        "waiting_time": status_data["waiting_time"],
        "status": "QUEUED",
    }), 200

@app.route("/metrics")
def metrics():
    SERVICE_UP.labels(service_name=SERVICE_NAME).set(1)
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5010, debug=True)
