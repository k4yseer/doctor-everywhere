import os
import requests
from datetime import datetime, timezone
from app import notification_publisher

QUEUE_SERVICE_URL = os.getenv("QUEUE_SERVICE_URL", "http://queue-service:5011")
TELECONFERENCING_URL = os.getenv("TELECONFERENCING_URL", "http://teleconferencing-wrapper:5006")
APPOINTMENT_SERVICE_URL = os.getenv("APPOINTMENT_SERVICE_URL", "http://appointment-service:5002")
PATIENT_SERVICE_URL = os.getenv("PATIENT_SERVICE_URL", "http://patient-service:5003")


class UpstreamError(Exception):
    def __init__(self, status_code, message, error_code):
        self.status_code = status_code
        self.message = message
        self.error_code = error_code


def _raise_for_connection(service_name, error_code):
    raise UpstreamError(503, f"{service_name} unreachable", error_code)


def _raise_for_status(res):
    try:
        message = res.json().get("message", "Upstream service error")
    except Exception:
        message = "Upstream service error"
    raise UpstreamError(res.status_code, message, f"CONSULT-{res.status_code}-UPSTREAM")


def handle_no_show(appointment_id):
    try:
        res = requests.get(f"{APPOINTMENT_SERVICE_URL}/appointments/{appointment_id}")
    except requests.exceptions.RequestException:
        _raise_for_connection("Appointment service", "CONSULT-503-APPT_UNREACHABLE")
    if not res.ok:
        _raise_for_status(res)
    patient_id = res.json()["data"]["patient_id"]

    try:
        res = requests.get(f"{PATIENT_SERVICE_URL}/patient/{patient_id}/details")
    except requests.exceptions.RequestException:
        _raise_for_connection("Patient service", "CONSULT-503-PATIENT_UNREACHABLE")
    if not res.ok:
        _raise_for_status(res)
    body = res.json()
    email = body.get("data", body).get("email")

    try:
        res = requests.put(
            f"{APPOINTMENT_SERVICE_URL}/appointments/{appointment_id}/status",
            json={"status": "NO_SHOW"},
        )
    except requests.exceptions.RequestException:
        _raise_for_connection("Appointment service", "CONSULT-503-APPT_UNREACHABLE")
    if not res.ok:
        _raise_for_status(res)

    notification_publisher.publish_notification("no-show", {"email": email, "appointment_id": appointment_id})


def dequeue_patient():
    try:
        res = requests.delete(f"{QUEUE_SERVICE_URL}/queue/head")
    except requests.exceptions.RequestException:
        _raise_for_connection("Queue service", "CONSULT-503-QUEUE_UNREACHABLE")
    if not res.ok:
        _raise_for_status(res)
    return res.json()["patient_id"]


def create_zoom_meeting():
    try:
        res = requests.post(
            f"{TELECONFERENCING_URL}/api/wrapper/zoom/meeting",
            json={
                "topic": "Doctor Consultation",
                "start_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
            },
        )
    except requests.exceptions.RequestException:
        _raise_for_connection("Teleconferencing service", "CONSULT-503-ZOOM_UNREACHABLE")
    if not res.ok:
        _raise_for_status(res)
    return res.json()["join_url"]


def create_appointment(patient_id, doctor_id, meet_link):
    try:
        res = requests.post(
            f"{APPOINTMENT_SERVICE_URL}/appointments",
            json={
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "slot_datetime": datetime.now(timezone.utc).isoformat(),
                "meet_link": meet_link,
            },
        )
    except requests.exceptions.RequestException:
        _raise_for_connection("Appointment service", "CONSULT-503-APPT_UNREACHABLE")
    if not res.ok:
        _raise_for_status(res)
    return res.json()["appointment_id"]


def get_patient_details(patient_id):
    try:
        res = requests.get(f"{PATIENT_SERVICE_URL}/patient/{patient_id}/details")
    except requests.exceptions.RequestException:
        _raise_for_connection("Patient service", "CONSULT-503-PATIENT_UNREACHABLE")
    if not res.ok:
        _raise_for_status(res)
    body = res.json()
    return body.get("data", body)


def notify_head_of_queue(email, meeting_link):
    notification_publisher.publish_notification("head-of-queue", {"email": email, "meeting_link": meeting_link})
