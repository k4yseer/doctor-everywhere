import json
import os

import pika

AMQP_URL = os.environ.get("AMQP_URL", "amqp://guest:guest@localhost:5672/")
EXCHANGE_NAME = "topic_logs"


def publish_error(source_service, error_code, error_message, payload=None):
    routing_key = f"{source_service}.error"
    message = {
        "source_service": source_service,
        "error_code": error_code,
        "error_message": error_message,
        "payload": payload or {},
    }

    try:
        connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=routing_key,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2),
        )
        connection.close()
    except Exception:
        # Never allow error publishing failure to break API flow.
        pass
