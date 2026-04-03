# Join Queue — Composite Service

Orchestrates a patient joining the walk-in consultation queue. It checks doctor availability via the Doctor Service, then creates a queue entry via the Queue Service, and returns the patient's position and estimated waiting time.

## Architecture

```
Client
  │
  ▼
POST /api/join-queue
  │
  ├─► GET /doctors?status=AVAILABLE       (Doctor Service :5001)
  │
  └─► POST /queue                         (Queue Service :5011)
        │
        ├─ 201 ──► 201 { queue_id, queue_position, waiting_time, status }
        │
        └─ 200 (already queued) ──► GET /queue/position/{patient_id}   (Queue Service :5011)
                     │
                     ▼
                   200 { queue_id, queue_position, waiting_time, status }

GET /api/join-queue/status/<patient_id>
  │
  ├─► GET /doctors?status=AVAILABLE       (Doctor Service :5001)
  │
  └─► GET /queue/position/{patient_id}   (Queue Service :5011)
        │
        ▼
      200 { queue_position, waiting_time, status }
```

5xx errors are published to RabbitMQ on the `join-queue.error` routing key (exchange: `topic_logs`).

## API

### `POST /api/join-queue`

Add a patient to the consultation queue.

**Request body**

| Field        | Type   | Required | Description        |
|--------------|--------|----------|--------------------|
| `patient_id` | string | yes      | Patient identifier |

```json
{ "patient_id": "10000001" }
```

**Responses**

| Status | Description                                                                     |
|--------|---------------------------------------------------------------------------------|
| 201    | Patient added to queue                                                          |
| 200    | Patient already in queue — current position returned                            |
| 400    | `patient_id` missing                                                            |
| 503    | Doctor service unreachable, queue service unreachable, or no doctors available  |

**201 response body** — patient newly added

```json
{
  "code": 201,
  "queue_id": 4,
  "queue_position": 3,
  "waiting_time": 20,
  "status": "QUEUED"
}
```

**200 response body** — patient already in queue

```json
{
  "code": 200,
  "queue_id": 3,
  "queue_position": 2,
  "waiting_time": 10,
  "status": "QUEUED"
}
```

`waiting_time` is in minutes, estimated from queue position and available doctor count.

---

### `GET /api/join-queue/status/<patient_id>`

Get a patient's current queue position and estimated wait time.

**Path parameters**

| Parameter    | Type   | Description        |
|--------------|--------|--------------------|
| `patient_id` | string | Patient identifier |

**Responses**

| Status | Description                                          |
|--------|------------------------------------------------------|
| 200    | Queue status retrieved                               |
| 404    | Patient not in queue                                 |
| 503    | Doctor service or queue service unreachable          |

**200 response body**

```json
{
  "code": 200,
  "queue_position": 2,
  "waiting_time": 10,
  "status": "QUEUED"
}
```

---

Interactive Swagger docs are available at `http://localhost:5010/apidocs`.

## Environment Variables

| Variable            | Default                              | Description                |
|---------------------|--------------------------------------|----------------------------|
| `DOCTOR_SERVICE_URL`| `http://doctor-service:5001`         | Base URL of Doctor Service |
| `QUEUE_SERVICE_URL` | `http://queue-service:5011`          | Base URL of Queue Service  |
| `AMQP_URL`          | `amqp://guest:guest@localhost:5672/` | RabbitMQ connection URL    |

## Running with Docker

```bash
docker build -t join-queue .
docker run -p 5010:5010 \
  -e DOCTOR_SERVICE_URL=http://doctor-service:5001 \
  -e QUEUE_SERVICE_URL=http://queue-service:5011 \
  -e AMQP_URL=amqp://guest:guest@rabbitmq:5672/ \
  join-queue
```

## Running Locally

```bash
pip install -r requirements.txt
FLASK_APP=app.main flask run --host=0.0.0.0 --port=5010
```

## Dependencies

| Package    | Version  | Purpose                          |
|------------|----------|----------------------------------|
| Flask      | 3.1.3    | Web framework                    |
| flasgger   | 0.9.7.1  | Swagger UI / OpenAPI docs        |
| requests   | 2.32.5   | HTTP calls to upstream services  |
| pika       | 1.3.2    | RabbitMQ error publishing        |
