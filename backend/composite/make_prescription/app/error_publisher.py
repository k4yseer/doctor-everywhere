import pika
import json
import os

AMQP_URL      = os.environ.get("AMQP_URL", "amqp://guest:guest@localhost:5672/")
EXCHANGE_NAME = "topic_logs"


def publish_error(source_service: str, error_code: str, error_message: str, payload: dict = None):
    routing_key = f"{source_service}.error"

    message = {
        "source_service": source_service,
        "error_code":     error_code,
        "error_message":  error_message,
        "payload":        payload or {}
    }

    try:
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        channel    = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=routing_key,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2)  # persistent
        )
        connection.close()
        print(f"[{source_service}] Error published → '{routing_key}': {error_code}")

    except Exception as e:
        # Never let error reporting crash the calling service
        print(f"[{source_service}] WARNING: Could not publish to AMQP — {e}")
        print(f"[{source_service}] Error details: {error_code} | {error_message}")
