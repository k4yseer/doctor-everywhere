# Teleconferencing Wrapper Microservice

A thin Flask wrapper around the **Zoom API** that handles meeting creation for the Doctor Everywhere appointment flow. It is called by the **Make Appointment** orchestrator service.

---

## How it fits in the system

```
Make Appointment orchestrator
        │
        │  POST /api/wrapper/zoom/meeting
        ▼
Teleconferencing Wrapper   ──►  Zoom API (Server-to-Server OAuth)
        │
        │  On error: publishes teleconferencing.error
        ▼
    AMQP Broker  ──►  Error service (consumes *.error)
```

1. The orchestrator sends a `POST` request with appointment details.
2. This service exchanges credentials for a short-lived Zoom OAuth token.
3. It calls the Zoom API to create a scheduled meeting.
4. The `join_url` and meeting credentials are returned to the orchestrator.
5. On any failure, a `TELECONFERENCING_ERROR` event is published to RabbitMQ so the Error service can log it.

---

## Endpoints

### `POST /api/wrapper/zoom/meeting`

Create a Zoom meeting and return the join URL.

**Request body**

| Field        | Type    | Required | Default          | Description                                      |
|-------------|---------|----------|------------------|--------------------------------------------------|
| `topic`      | string  | yes      | —                | Meeting title, e.g. `"Consultation with Dr. Lee"` |
| `start_time` | string  | yes      | —                | ISO 8601 datetime, e.g. `"2026-03-14T10:00:00"` |
| `duration`   | integer | no       | `30`             | Duration in minutes                              |
| `timezone`   | string  | no       | `Asia/Singapore` | IANA timezone name                               |

**Example request**

```json
{
  "topic": "Consultation with Dr. Lee",
  "start_time": "2026-03-14T10:00:00",
  "duration": 30,
  "timezone": "Asia/Singapore"
}
```

**Success response (200)**

```json
{
  "success": true,
  "meeting_id": 123456789,
  "join_url": "https://zoom.us/j/123456789?pwd=...",
  "password": "abc123",
  "start_time": "2026-03-14T10:00:00Z",
  "duration": 30,
  "topic": "Consultation with Dr. Lee"
}
```

**Error response (400 / 500)**

```json
{
  "success": false,
  "error": "Missing required fields: 'topic' and 'start_time'"
}
```

---

### `GET /health`

Returns `{"status": "ok"}` — used by Docker / load balancers to verify the service is alive.

---

### `GET /apidocs`

Interactive Swagger UI for the full API documentation.

---

## Environment variables

Set these in `backend/.env` (see `.env.example`):

| Variable             | Description                                      |
|----------------------|--------------------------------------------------|
| `ZOOM_ACCOUNT_ID`    | Zoom Server-to-Server OAuth Account ID           |
| `ZOOM_CLIENT_ID`     | Zoom OAuth App Client ID                         |
| `ZOOM_CLIENT_SECRET` | Zoom OAuth App Client Secret                     |
| `ZOOM_WRAPPER_PORT`  | Port the service listens on (default `5006`)     |
| `RABBITMQ_URL`       | AMQP connection string (default `amqp://guest:guest@rabbitmq:5672/`) |

### Getting Zoom credentials

1. Go to [Zoom Marketplace](https://marketplace.zoom.us/) and sign in.
2. Click **Develop → Build App** and choose **Server-to-Server OAuth**.
3. Create the app and note the **Account ID**, **Client ID**, and **Client Secret**.
4. Under **Scopes**, add `meeting:write:admin` (or `meeting:write` for user-level).
5. Activate the app.

---

## Running locally

### With Docker Compose (recommended)

From the `backend/` directory:

```bash
docker compose up --build teleconferencing-wrapper
```

### Standalone

```bash
cd backend/atomic/teleconferencing_wrapper
pip install -r requirements.txt
ZOOM_ACCOUNT_ID=... ZOOM_CLIENT_ID=... ZOOM_CLIENT_SECRET=... python app/main.py
```

---

## File structure

```
teleconferencing_wrapper/
├── app/
│   └── main.py          # Flask app — Zoom API calls, AMQP error publishing
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## Dependencies

| Package      | Version  | Purpose                         |
|-------------|----------|---------------------------------|
| Flask        | 3.0.2    | HTTP framework                  |
| flasgger     | 0.9.7.1  | Swagger UI / OpenAPI docs       |
| requests     | 2.31.0   | HTTP calls to Zoom API          |
| pika         | 1.3.2    | AMQP client for RabbitMQ        |
