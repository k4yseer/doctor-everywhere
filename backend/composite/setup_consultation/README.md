# Setup Consultation — Composite Service

Orchestrates the full consultation setup for a doctor's next patient: dequeues the next patient, creates a Zoom meeting, records the appointment, fetches patient details, and notifies the patient with the meeting link. A separate endpoint handles marking the previous patient as a no-show.

## Architecture

```
Client
  │
  ├─► POST /api/setup-consultation/no-show
  │     │
  │     ├─► GET /appointments/:id            (Appointment Service :5002)
  │     ├─► GET /patient/:id/details         (Patient Service :5003)
  │     ├─► PUT /appointments/:id/status     (Appointment Service :5002)  ← mark NO_SHOW
  │     └─► AMQP publish notification.no-show        (RabbitMQ → notification_queue)
  │
  └─► POST /api/setup-consultation/next-patient
        │
        ├─► DELETE /queue/head                        (Queue Service :5011)
        ├─► POST /api/wrapper/zoom/meeting            (Teleconferencing Wrapper :5006)
        ├─► POST /appointments                        (Appointment Service :5002)
        ├─► GET /patient/:id/details                  (Patient Service :5003)
        └─► AMQP publish notification.head-of-queue   (RabbitMQ → notification_queue)
              │
              ▼
          200 { code, patient, appointment_id, meet_link, start_url }
```

5xx errors are published to RabbitMQ on the `consultation-setup.error` routing key (exchange: `topic_logs`).

## API

### `POST /api/setup-consultation/next-patient`

Dequeue the next patient and set up the consultation.

**Request body**

| Field       | Type    | Required | Description                              |
|-------------|---------|----------|------------------------------------------|
| `doctor_id` | integer | yes      | ID of the doctor starting the consultation |

```json
{ "doctor_id": 1 }
```

**Responses**

| Status | Description                                                        |
|--------|--------------------------------------------------------------------|
| 200    | Consultation setup successful                                      |
| 400    | `doctor_id` missing                                                |
| 404    | Queue is empty                                                     |
| 503    | Upstream service unreachable                                       |
| 500    | Unexpected server error                                            |

**200 response body**

```json
{
  "code": 200,
  "patient": { "patient_id": 1, "patient_name": "Jane Doe", "email": "jane@example.com" },
  "appointment_id": 7,
  "meet_link": "https://zoom.us/j/123456789",
  "start_url": "https://zoom.us/s/123456789?zak=abc"
}
```

---

### `POST /api/setup-consultation/no-show`

Mark an existing appointment as a no-show and notify the patient via RabbitMQ.

**Request body**

| Field            | Type    | Required | Description                              |
|------------------|---------|----------|------------------------------------------|
| `appointment_id` | integer | yes      | ID of the appointment to mark as no-show |

```json
{ "appointment_id": 42 }
```

**Responses**

| Status | Description                                       |
|--------|---------------------------------------------------|
| 200    | Appointment marked as no-show                     |
| 400    | `appointment_id` missing                          |
| 503    | Upstream appointment or patient service unreachable |

**200 response body**

```json
{ "code": 200, "message": "Appointment 42 marked as no-show" }
```

---

Interactive Swagger docs are available at `http://localhost:5012/apidocs`.

## Environment Variables

| Variable                   | Default                                    | Description                           |
|----------------------------|--------------------------------------------|---------------------------------------|
| `QUEUE_SERVICE_URL`        | `http://queue-service:5011`                | Base URL of Queue Service             |
| `TELECONFERENCING_URL`     | `http://teleconferencing-wrapper:5006`     | Base URL of Teleconferencing Wrapper  |
| `APPOINTMENT_SERVICE_URL`  | `http://appointment-service:5002`          | Base URL of Appointment Service       |
| `PATIENT_SERVICE_URL`      | `http://patient-service:5003`              | Base URL of Patient Service           |
| `AMQP_URL`                 | `amqp://guest:guest@localhost:5672/`       | RabbitMQ connection URL               |

## Running with Docker

```bash
docker build -t consultation-setup .
docker run -p 5012:5012 \
  -e QUEUE_SERVICE_URL=http://queue-service:5011 \
  -e TELECONFERENCING_URL=http://teleconferencing-wrapper:5006 \
  -e APPOINTMENT_SERVICE_URL=http://appointment-service:5002 \
  -e PATIENT_SERVICE_URL=http://patient-service:5003 \
  -e AMQP_URL=amqp://guest:guest@rabbitmq:5672/ \
  consultation-setup
```

## Running Locally

```bash
pip install -r requirements.txt
FLASK_APP=app.main flask run --host=0.0.0.0 --port=5012
```

## Dependencies

| Package    | Version  | Purpose                         |
|------------|----------|---------------------------------|
| Flask      | 3.1.3    | Web framework                   |
| flasgger   | 0.9.7.1  | Swagger UI / OpenAPI docs       |
| requests   | 2.32.5   | HTTP calls to upstream services |
| pika       | 1.3.2    | RabbitMQ error and notification publishing |
