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
