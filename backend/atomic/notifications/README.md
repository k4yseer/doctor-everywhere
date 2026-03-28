# Notifications Service

## Overview

A pure AMQP consumer service that listens for notification events on RabbitMQ and delivers transactional emails via [Resend](https://resend.com).

---

## Architecture

| Component | Value |
|-----------|-------|
| **Exchange** | `notifications` (topic, durable) |
| **Queue** | `notification_queue` (durable) |
| **Routing key pattern** | `notification.#` |
| **Email provider** | Resend |

---

## Notification Types

| Type | Routing Key | Required Fields |
|------|-------------|-----------------|
| `head-of-queue` | `notification.head-of-queue` | `email`, `meeting_link` |
| `no-show` | `notification.no-show` | `email`, `appointment_id` |
| `payment-details` | `notification.payment-details` | `email`, `appointment_id`, `is_successful` |
| `send-mc` | `notification.send-mc` | `email`, `appointment_id`, `filename`, `file_content` (base64) |

---

## Publishing Notifications (from another service)

Copy `app/notification_publisher.py` into the consuming service, then:

```python
from notification_publisher import publish_notification

publish_notification("head-of-queue", {
    "email": "patient@example.com",
    "meeting_link": "https://meet.example.com/abc123"
})
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `RESEND_API_KEY` | Resend API key |
| `DOMAIN_NAME` | Sender domain (e.g. `example.com`) |
| `AMQP_URL` | RabbitMQ connection URL (default: `amqp://guest:guest@localhost:5672/`) |

---

## Running Locally

```bash
# From backend/
docker compose up --build notification-service
```

Service runs on port **5004** (no accessible HTTP routes — port is a Flask keep-alive only).

---

## Error Reporting

Failures publish to the `topic_logs` exchange with routing key `notification.error` via `error_publisher.py`.

| Error Code | Meaning |
|------------|---------|
| `NOTIF-500` | Message processing failure |
| `NOTIF-503` | AMQP connection failure |
