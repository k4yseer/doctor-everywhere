import os
import base64
import json
import requests
import pika
from flask import Flask, request, jsonify
from flasgger import Swagger
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
swagger = Swagger(app, template={
    "info": {
        "title": "Teleconferencing Wrapper Microservice API",
        "version": "1.0.0",
        "description": (
            "Thin wrapper around the Zoom API. "
            "Authenticates via Server-to-Server OAuth and creates Zoom meetings, "
            "returning the join URL to the Make Appointment orchestrator."
        )
    }
})

ZOOM_ACCOUNT_ID    = os.getenv("ZOOM_ACCOUNT_ID")
ZOOM_CLIENT_ID     = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")
RABBITMQ_URL       = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
SERVICE_NAME = "teleconferencing-wrapper"
SERVICE_UP = Gauge("service_up", "1 if service is up, 0 otherwise", ["service_name"])


# ── Zoom helpers ──────────────────────────────────────────────────────────────

def _get_zoom_access_token() -> str:
    """Exchange account credentials for a short-lived Zoom access token."""
    credentials = base64.b64encode(
        f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}".encode()
    ).decode()

    resp = requests.post(
        "https://zoom.us/oauth/token",
        params={"grant_type": "account_credentials", "account_id": ZOOM_ACCOUNT_ID},
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _create_zoom_meeting(access_token: str, topic: str, start_time: str,
                          duration: int, timezone: str) -> dict:
    """Call the Zoom Create Meeting API and return the raw response body."""
    resp = requests.post(
        "https://api.zoom.us/v2/users/me/meetings",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={
            "topic": topic,
            "type": 2,                  # scheduled meeting
            "start_time": start_time,   # ISO 8601, e.g. "2026-03-14T10:00:00"
            "duration": duration,
            "timezone": timezone,
            "settings": {
                "host_video": True,
                "participant_video": True,
                "join_before_host": False,
                "waiting_room": True,
            },
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


# ── AMQP error publisher ──────────────────────────────────────────────────────

def _publish_error(error_code: str, error_message: str, payload: dict = None) -> None:
    """Best-effort publish of a teleconferencing.error event to the broker."""
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        conn   = pika.BlockingConnection(params)
        ch     = conn.channel()
        ch.exchange_declare(exchange="topic_logs", exchange_type="topic", durable=True)
        ch.basic_publish(
            exchange="topic_logs",
            routing_key="teleconferencing.error",
            body=json.dumps({
                "source_service": "teleconferencing-wrapper",
                "error_code":     error_code,
                "error_message":  error_message,
                "payload":        payload,
            }),
            properties=pika.BasicProperties(
                delivery_mode=2,        # persistent
                content_type="application/json",
            ),
        )
        conn.close()
    except Exception:
        pass    # never let broker unavailability crash the HTTP response


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.route("/api/wrapper/zoom/meeting", methods=["POST"])
def create_meeting():
    """
    Create a Zoom meeting and return the join URL
    ---
    description: >
      Called by the Make Appointment orchestrator (step 3b). Authenticates with
      Zoom via Server-to-Server OAuth, creates a scheduled meeting, and returns
      the join URL and credentials. On failure, a TELECONFERENCING_ERROR event
      is published to the AMQP broker (routing key: teleconferencing.error).
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - topic
            - start_time
          properties:
            topic:
              type: string
              description: Meeting topic / title
              example: "Consultation with Dr. Smith"
            start_time:
              type: string
              description: "ISO 8601 datetime (no timezone suffix — use the timezone field)"
              example: "2026-03-14T10:00:00"
            duration:
              type: integer
              description: Duration in minutes (default 30)
              example: 30
            timezone:
              type: string
              description: IANA timezone name (default Asia/Singapore)
              example: "Asia/Singapore"
    responses:
      200:
        description: Meeting created successfully
        schema:
          type: object
          properties:
            success:
              type: boolean
            meeting_id:
              type: integer
            join_url:
              type: string
            start_url:
              type: string
            password:
              type: string
            start_time:
              type: string
            duration:
              type: integer
            topic:
              type: string
      400:
        description: Missing required fields
        schema:
          type: object
          properties:
            success:
              type: boolean
            error:
              type: string
      500:
        description: Zoom API or server error
        schema:
          type: object
          properties:
            success:
              type: boolean
            error:
              type: string
    """
    data = request.get_json()

    topic      = data.get("topic")      if data else None
    start_time = data.get("start_time") if data else None
    duration   = data.get("duration",  30)
    timezone   = data.get("timezone",  "Asia/Singapore")

    if not topic or not start_time:
        return jsonify({
            "success": False,
            "error": "Missing required fields: 'topic' and 'start_time'"
        }), 400

    if not isinstance(duration, int) or duration <= 0:
        return jsonify({
            "success": False,
            "error": "'duration' must be a positive integer (minutes)"
        }), 400

    try:
        token   = _get_zoom_access_token()
        meeting = _create_zoom_meeting(token, topic, start_time, duration, timezone)

        return jsonify({
            "success":    True,
            "meeting_id": meeting["id"],
            "join_url":   meeting["join_url"],
            "start_url":  meeting["start_url"],
            "password":   meeting.get("password", ""),
            "start_time": meeting.get("start_time"),
            "duration":   meeting.get("duration"),
            "topic":      meeting.get("topic"),
        }), 200

    except requests.HTTPError as e:
        error_msg = f"Zoom API error: {e.response.status_code} {e.response.text}"
        _publish_error(
            error_code="ZOOM-500",
            error_message=error_msg,
            payload={"topic": topic, "start_time": start_time},
        )
        return jsonify({"success": False, "error": error_msg}), 500

    except Exception as e:
        error_msg = str(e)
        _publish_error(
            error_code="ZOOM-500",
            error_message=error_msg,
            payload={"topic": topic, "start_time": start_time},
        )
        return jsonify({"success": False, "error": "Failed to create Zoom meeting."}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200

@app.route("/metrics")
def metrics():
    SERVICE_UP.labels(service_name=SERVICE_NAME).set(1)
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == "__main__":
    port = int(os.getenv("ZOOM_WRAPPER_PORT", 5006))
    app.run(host="0.0.0.0", port=port, debug=True)
