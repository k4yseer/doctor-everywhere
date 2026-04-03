import pika
import json
import os

AMQP_URL = os.environ.get("AMQP_URL", "amqp://guest:guest@localhost:5672/")
EXCHANGE_NAME = "topic_logs"

connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
channel = connection.channel()

# Ensure exchange exists
channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)

# Ensure queue exists and is bound — must match error service exactly
channel.queue_declare(queue="error_queue", durable=True)
channel.queue_bind(exchange=EXCHANGE_NAME, queue="error_queue", routing_key="*.error")

messages = [
    {
        "routing_key": "test.error",
        "body": {
            "source_service": "test_service",
            "error_code": "TEST-500",
            "error_message": "This is a test error",
            "payload": {"test": True}
        }
    },
    {
        "routing_key": "appointment.error",
        "body": {
            "source_service": "appointment_service",
            "error_code": "APPT-500",
            "error_message": "Failed to create appointment record",
            "payload": {"appointment_id": 1234}
        }
    }
]

for msg in messages:
    channel.basic_publish(
        exchange=EXCHANGE_NAME,
        routing_key=msg["routing_key"],
        body=json.dumps(msg["body"]),
        properties=pika.BasicProperties(delivery_mode=2)  # make messages persistent
    )
    print(f"Sent message to '{msg['routing_key']}'")

connection.close()
