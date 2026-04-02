# delivery_payment_success_consumer.py

import threading
import time
import json
import uuid
import pika
from flask import current_app as app
from sqlalchemy.orm import sessionmaker
from app.models import Delivery, engine  # <-- replace with your actual module path


# RabbitMQ config
AMQP_URL = "amqp://guest:guest@rabbitmq:5672/"
EXCHANGE_NAME = "topic_logs"
PAYMENT_SUCCESS_ROUTING_KEY = "payment.success"
QUEUE_NAME = "delivery.payment.success"
DLX_NAME = EXCHANGE_NAME
DLQ_QUEUE = "delivery.payment.success.dlq"
DLQ_ROUTING_KEY = "delivery.payment.success.dlq"


def process_payment_success(ch, method, properties, body):
    try:
        payload = json.loads(body)
        if payload.get("event_type") != "payment.success":
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        appointment_id = payload.get("appointment_id")
        patient_address = payload.get("patient_address")

        if not appointment_id or not patient_address:
            app.logger.warning("payment.success missing appointment_id or patient_address")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        Session = sessionmaker(bind=engine)
        session = Session()
        try:
            existing = session.query(Delivery).filter_by(appointment_id=str(appointment_id)).first()
            if existing:
                app.logger.info(f"Delivery already exists for appointment_id={appointment_id}")
            else:
                delivery = Delivery(
                    delivery_id=str(uuid.uuid4()),
                    appointment_id=str(appointment_id),
                    patient_address=patient_address,
                    delivery_status="PENDING",
                )
                session.add(delivery)
                session.commit()
                app.logger.info(f"Created delivery for appointment_id={appointment_id}")
        except Exception:
            session.rollback()
            app.logger.exception("Failed to create delivery from payment.success event")
        finally:
            session.close()

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception:
        app.logger.exception("Error processing payment.success message")
        ch.basic_ack(delivery_tag=method.delivery_tag)


def start_amqp_consumer():
    """Start the RabbitMQ consumer in a loop with exponential backoff."""
    delay = 5
    while True:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
            channel = connection.channel()

            # Declare main exchange
            channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)

            # Declare queue with DLX safely
            queue_args = {
                "x-dead-letter-exchange": DLX_NAME,
                "x-dead-letter-routing-key": DLQ_ROUTING_KEY,
            }
            channel.queue_declare(queue=QUEUE_NAME, durable=True, arguments=queue_args)
            channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key=PAYMENT_SUCCESS_ROUTING_KEY)

            # Declare Dead Letter Queue
            channel.queue_declare(queue=DLQ_QUEUE, durable=True)
            channel.queue_bind(exchange=DLX_NAME, queue=DLQ_QUEUE, routing_key=DLQ_ROUTING_KEY)

            # Start consuming
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=process_payment_success)
            app.logger.info("Delivery service AMQP consumer started, waiting for messages...")
            channel.start_consuming()

        except Exception:
            app.logger.exception("Delivery service AMQP consumer error, retrying...")
            time.sleep(delay)
            delay = min(delay * 2, 60)


# Start consumer in a background thread when Flask app starts
def run_consumer_in_background():
    t = threading.Thread(target=start_amqp_consumer, daemon=True)
    t.start()