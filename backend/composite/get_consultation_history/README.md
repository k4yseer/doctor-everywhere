# Get Consultation History — Composite Service

Stateless BFF that aggregates appointment, prescription, invoice and delivery information into a single consultation-history JSON payload for a patient.

Service file: `backend/composite/get_consultation_history/app/main.py`

## Endpoint
- `GET /consultation-history/<patient_id>` — returns an array of consultation objects. Each object includes `appointment_id`, `date`, `status`, `mc`, `prescriptions`, and `billing`.

## Environment
- `appointmentURL` (default: `http://appointment-service:5002`)
- `invoiceURL` (default: `http://invoice-service:5005`)
- `deliveryURL` (default: `http://delivery-service:5008`)
- `prescriptionURL` (external API)
- `AMQP_URL` (RabbitMQ)

## How it works (brief)
- Requests `GET /appointments/patient/{patient_id}` from the Appointment Service.
- For each appointment, fetches prescription (external), invoice and delivery details (with fallbacks).
- Assembles the aggregated object per appointment and returns an array to the client.
- Errors (5xx/unhandled) are published to RabbitMQ so the Error Service can persist them.

## Architecture (high-level)

Components:
- Client (frontend)
- Get Consultation History (this composite, port `5013`)
- Appointment Service (`/appointments/patient/{id}`)
- Prescription API (external)
- Invoice Service
- Delivery Service
- RabbitMQ (`topic_logs` exchange) and Error Service (consumes and persists errors)

Sequence (typical request):
1. Client -> Composite: `GET /consultation-history/{patient_id}`
2. Composite -> Appointment Service
3. For each appointment: Composite -> Prescription / Invoice / Delivery
4. Composite -> Client with aggregated JSON
5. Any internal/5xx errors -> publish to RabbitMQ -> Error Service

Simple ASCII flow:

```
Client
  │
  ▼
GET /consultation-history/{patient_id}
  │
  ├─► GET /appointments/patient/{patient_id}  (Appointment Service :5002)
  │
  └─► For each appointment:
        ├─► GET PrescriptionAPI (external)
        ├─► GET /invoices/appointment/{id}     (Invoice Service :5005)
        └─► GET /deliveries/appointment/{id}   (Delivery Service :5008)
              │
              ▼
        Composite aggregates and returns 200 [ { appointment, mc, prescriptions, billing } ]
```

## Run (docker-compose)
From the `backend` folder:

```sh
docker compose -f compose.yaml up -d rabbitmq appointment-service invoice-service delivery-service get-consultation-history-service
```

Test:

```sh
curl -s http://localhost:5013/consultation-history/1 | jq .
```

## Troubleshooting
- If you get an empty array: verify `appointment-service` returns appointments:
  `curl -s http://localhost:5002/appointments/patient/1 | jq .`
- If composite returns 500: check logs:
  `docker compose -f compose.yaml logs --tail=200 get-consultation-history-service`
- Ensure `AMQP_URL`/RabbitMQ are running for error publishing.

## Related composites
- Join Queue: `backend/composite/join_queue/README.md`
- Setup Consultation: `backend/composite/setup_consultation/README.md`

## Run locally (with compose)
From the `backend` folder:

```sh
docker compose -f compose.yaml up -d rabbitmq appointment-service invoice-service delivery-service get-consultation-history-service
```

Then test:

```sh
# aggregated view for patient 1
curl -s http://localhost:5013/consultation-history/1 | jq .
```

## Troubleshooting
- If you get an empty array, verify `appointment-service` returns appointments for the patient:
  `curl -s http://localhost:5002/appointments/patient/1 | jq .`
- If composite returns 500, check its logs:
  `docker compose -f compose.yaml logs --tail=200 get-consultation-history-service`
- Ensure RabbitMQ is running if you expect error messages to be published.

## Notes
- The service is intentionally tolerant: missing upstreams return partial results rather than failing the whole request.
- For production, run behind a WSGI server (gunicorn) and add healthchecks/timeouts according to SLAs.
