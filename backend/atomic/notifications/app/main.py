from flask import Flask
from app import emails
from app.error_publisher import publish_error
import pika
import json
import os
import threading
import base64
import time
from urllib import request as urllib_request, error as urllib_error
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST

AMQP_URL = os.environ.get("AMQP_URL", "amqp://guest:guest@localhost:5672/")
EXCHANGE_NAME = "notifications"
QUEUE_NAME = "notification_queue"
ROUTING_KEY = "notification.#"
PATIENT_SERVICE_URL = os.environ.get("PATIENT_SERVICE_URL", "http://patient:5003")
PAYMENT_SUCCESS_ROUTING_KEY = "payment.success"
PAYMENT_SUCCESS_QUEUE = "notification_payment_success_queue"
SERVICE_NAME = "notifications"
SERVICE_UP = Gauge("service_up", "1 if service is up, 0 otherwise", ["service_name"])

app = Flask(__name__)


def process_notification_message(ch, method, properties, body):
    try:
        data = json.loads(body)
        notification_type = data.get("type")
        email = data.get("email")

        if notification_type == "head-of-queue":
            meeting_link = data.get("meeting_link")
            emails.head_of_queue(email, meeting_link)
        elif notification_type == "no-show":
            appointment_id = data.get("appointment_id")
            emails.no_show(email, appointment_id)
        elif notification_type == "payment-details":
            appointment_id = data.get("appointment_id")
            is_successful = data.get("is_successful")
            emails.payment_details(email, appointment_id, is_successful)
        elif notification_type == "send-mc":
            appointment_id = data.get("appointment_id")
            filename = data.get("filename")
            file_bytes = base64.b64decode(data.get("file_content"))
            emails.send_mc(email, appointment_id, file_bytes, filename)
        else:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        publish_error(
            source_service="notification",
            error_code="NOTIF-500",
            error_message=f"Failed to process notification message: {e}",
            payload={"body": body.decode("utf-8", errors="replace")}
        )
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_amqp_consumer():
    delay = 5
    while True:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
            channel = connection.channel()

            channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)

            result = channel.queue_declare(queue=QUEUE_NAME, durable=True)
            queue_name = result.method.queue

            channel.queue_bind(exchange=EXCHANGE_NAME, queue=queue_name, routing_key=ROUTING_KEY)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=queue_name, on_message_callback=process_notification_message)

            print("[*] Waiting for messages.")
            delay = 5  # reset backoff on successful connection
            channel.start_consuming()

        except Exception as e:
            publish_error(
                source_service="notification",
                error_code="NOTIF-503",
                error_message=f"AMQP connection failed: {e}",
            )
            time.sleep(delay)
            delay = min(delay * 2, 60)


t = threading.Thread(target=start_amqp_consumer, daemon=True)
t.start()

@app.route("/metrics")
def metrics():
    SERVICE_UP.labels(service_name=SERVICE_NAME).set(1)
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004, debug=False)