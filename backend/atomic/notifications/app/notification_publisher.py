"""
Shared helper — copy into any service that needs to send notifications.

Usage:
    from notification_publisher import publish_notification

    # Notify patient they are head of queue
    publish_notification("head-of-queue", {
        "email": "patient@example.com",
        "meeting_link": "https://meet.example.com/abc123"
    })

    # Notify patient of no-show
    publish_notification("no-show", {
        "email": "patient@example.com",
        "appointment_id": "APT-001"
    })

    # Notify patient of payment outcome
    publish_notification("payment-details", {
        "email": "patient@example.com",
        "appointment_id": "APT-001",
        "is_successful": True
    })

    # Send MC to patient
    publish_notification("send-mc", {
        "email": "patient@example.com",
        "appointment_id": "APT-001",
        "filename": "mc.pdf",
        "file_content": "<base64-encoded bytes>"
    })

Routing key format: notification.<type>
Exchange: notifications (topic, durable)
"""

import pika
import json
import os

AMQP_URL = os.environ.get("AMQP_URL", "amqp://guest:guest@localhost:5672/")
EXCHANGE_NAME = "notifications"


def publish_notification(notification_type: str, payload: dict):
    routing_key = f"notification.{notification_type}"
    message = {"type": notification_type, **payload}

    try:
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
        channel.queue_declare(queue="notification_queue", durable=True)
        channel.queue_bind(exchange=EXCHANGE_NAME, queue="notification_queue", routing_key="notification.#")
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=routing_key,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        connection.close()
        print(f"[NOTIFICATION PUBLISHER] Published '{notification_type}' → '{routing_key}'")

    except Exception as e:
        print(f"[NOTIFICATION PUBLISHER] WARNING: Could not publish to AMQP — {e}")
