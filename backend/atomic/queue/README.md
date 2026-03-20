# Queue Service

Atomic microservice that manages the patient consultation queue.

- **Port:** `5011`
- **Swagger UI:** `http://localhost:5011/apidocs`

## Endpoints

### `POST /queue`
Add a patient to the queue. Returns a 409 if the patient is already queued.

**Request body:**
```json
{ "patient_id": "10000001" }
```

**Response `201`:**
```json
{ "code": 201, "queue_id": 4, "queue_position": 4 }
```

---

### `GET /queue/position/<patient_id>`
Get a patient's current position in the queue (1-indexed, ordered by join time).

**Response `200`:**
```json
{ "code": 200, "patient_id": "10000001", "queue_position": 2 }
```

---

### `DELETE /queue/head`
Remove the patient at the front of the queue and return their ID. Used by downstream services when a consultation begins.

**Response `200`:**
```json
{ "code": 200, "patient_id": "10000001" }
```
