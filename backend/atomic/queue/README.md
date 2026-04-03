# Queue Service

Atomic microservice that manages the patient consultation queue.

- **Port:** `5011`
- **Swagger UI:** `http://localhost:5011/apidocs`

## Endpoints

### `GET /queue`

Get all patients currently in the queue, ordered by arrival time.

**Response `200`:**
```json
{
  "code": 200,
  "data": [
    { "id": 1, "patient_id": "10000001", "created_at": "2024-01-01T10:00:00+00:00" },
    { "id": 2, "patient_id": "10000002", "created_at": "2024-01-01T10:05:00+00:00" }
  ]
}
```

---

### `POST /queue`

Add a patient to the queue. Returns a 200 if the patient is already queued.

**Request body:**
```json
{ "patient_id": "10000001" }
```

**Response `201` — patient newly added:**
```json
{ "code": 201, "queue_id": 4, "queue_position": 4, "data": { "id": 4, "patient_id": "10000001", "created_at": "2024-01-01T10:00:00+00:00" } }
```

**Response `200` — patient already in queue:**
```json
{ "code": 200, "queue_id": 3, "queue_position": 2 }
```

---

### `GET /queue/position/<patient_id>`

Get a patient's current position in the queue (1-indexed, ordered by join time).

**Response `200`:**
```json
{ "code": 200, "patient_id": "10000001", "queue_id": 3, "queue_position": 2 }
```

**Response `404`:** Patient not found in queue.

---

### `DELETE /queue/head`

Remove the patient at the front of the queue and return their ID. Used by downstream services when a consultation begins.

**Response `200`:**
```json
{ "code": 200, "patient_id": "10000001" }
```

**Response `404`:** Queue is empty.

---

### `DELETE /queue/<entry_id>`

Remove a specific patient from the queue by their entry ID.

**Response `200`:**
```json
{ "code": 200, "message": "Queue entry removed" }
```

**Response `404`:** Queue entry not found.
