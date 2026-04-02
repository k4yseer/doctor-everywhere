import json
import logging
import os
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime

import pika

# Configuration
AMQP_URL = os.environ.get("AMQP_URL", "amqp://guest:guest@rabbitmq:5672/")
EXCHANGE_NAME = os.environ.get("EXCHANGE_NAME", "topic_logs")
ROUTING_KEY = os.environ.get("ROUTING_KEY", "payment.success")
QUEUE_NAME = os.environ.get("QUEUE_NAME", "notification.payment.success")
DLX_NAME = os.environ.get("DLX_NAME", EXCHANGE_NAME)
DLQ_ROUTING_KEY = os.environ.get("DLQ_ROUTING_KEY", "notification.payment.success.dlq")
DLQ_QUEUE = os.environ.get("DLQ_QUEUE", "notification.payment.success.dlq")

NOTIFICATION_SERVICE_URL = os.environ.get("NOTIFICATION_SERVICE_URL", "http://localhost:5004")
EVENT_STORE_PATH = os.environ.get("EVENT_STORE_PATH", "notification_payment_success_events.db")

RETRY_DELAY_SECONDS = int(os.environ.get("RETRY_DELAY_SECONDS", "5"))
MAX_HTTP_RETRIES = int(os.environ.get("MAX_HTTP_RETRIES", "3"))
HTTP_TIMEOUT = int(os.environ.get("HTTP_TIMEOUT", "10"))

class CorrelationFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"
        return True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(correlation_id)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logger.addFilter(CorrelationFilter())


class CorrelationLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        correlation_id = self.extra.get("correlation_id", "no-correlation")
        kwargs.setdefault("extra", {})
        kwargs["extra"]["correlation_id"] = correlation_id
        return msg, kwargs


class EventStore:
    """Simple idempotency store for processed correlation IDs."""

    def __init__(self, path: str):
        self.path = path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.path)
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS processed_events ("
                "correlation_id TEXT PRIMARY KEY, "
                "event_type TEXT NOT NULL, "
                "appointment_id INTEGER, "
                "received_at TEXT NOT NULL"
                ")"
            )
            conn.commit()
        finally:
            conn.close()

    def is_processed(self, correlation_id: str) -> bool:
        conn = sqlite3.connect(self.path)
        try:
            cursor = conn.execute(
                "SELECT 1 FROM processed_events WHERE correlation_id = ?",
                (correlation_id,),
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def mark_processed(self, correlation_id: str, event_type: str, appointment_id: int):
        conn = sqlite3.connect(self.path)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO processed_events (correlation_id, event_type, appointment_id, received_at) VALUES (?, ?, ?, ?)",
                (correlation_id, event_type, appointment_id, datetime.utcnow().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()


class PaymentSuccessConsumer:
    def __init__(self):
        self.event_store = EventStore(EVENT_STORE_PATH)
        self.logger = CorrelationLoggerAdapter(logger, {"correlation_id": "-"})

    def connect(self):
        parameters = pika.URLParameters(AMQP_URL)
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)

        queue_args = {
            "x-dead-letter-exchange": DLX_NAME,
            "x-dead-letter-routing-key": DLQ_ROUTING_KEY,
        }
        channel.queue_declare(queue=QUEUE_NAME, durable=True, arguments=queue_args)
        channel.queue_bind(exchange=EXCHANGE_NAME, queue=QUEUE_NAME, routing_key=ROUTING_KEY)

        channel.queue_declare(queue=DLQ_QUEUE, durable=True)
        channel.queue_bind(exchange=DLX_NAME, queue=DLQ_QUEUE, routing_key=DLQ_ROUTING_KEY)

        return connection, channel

    def run(self):
        while True:
            try:
                connection, channel = self.connect()
                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(queue=QUEUE_NAME, on_message_callback=self.on_message)
                self.logger.info("Waiting for payment.success events")
                channel.start_consuming()
            except Exception as exc:
                self.logger.error(f"AMQP connection failed: {exc}")
                time.sleep(RETRY_DELAY_SECONDS)

    def on_message(self, ch, method, properties, body):
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.logger.error("Malformed JSON payload, sending to DLQ")
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
            return

        correlation_id = payload.get("correlation_id") or "missing-correlation"
        self.logger = CorrelationLoggerAdapter(logger, {"correlation_id": correlation_id})
        self.logger.info("Received payment.success event")

        if payload.get("event_type") != "payment.success":
            self.logger.info("Skipping non-payment.success event")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        if self._is_duplicate(correlation_id):
            self.logger.info("Duplicate event, acknowledging without replay")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        try:
            self.handle_event(payload)
            self.event_store.mark_processed(correlation_id, payload.get("event_type", "unknown"), payload.get("appointment_id"))
            self.logger.info("Event processed successfully")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except RetryableException as exc:
            self.logger.error(f"Retryable failure: {exc}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        except FatalException as exc:
            self.logger.error(f"Fatal failure: {exc}, sending to DLQ")
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as exc:
            self.logger.exception(f"Unexpected failure: {exc}")
            ch.basic_reject(delivery_tag=method.delivery_tag, requeue=False)

    def _is_duplicate(self, correlation_id: str) -> bool:
        if not correlation_id:
            return False
        return self.event_store.is_processed(correlation_id)

    def handle_event(self, payload: dict):
        appointment_id = payload.get("appointment_id")
        if appointment_id is None:
            raise FatalException("Missing appointment_id")
        if not isinstance(appointment_id, int):
            raise FatalException("appointment_id must be an integer")

        self.logger.info(f"Sending payment notification for appointment {appointment_id}")
        notify_url = f"{NOTIFICATION_SERVICE_URL.rstrip('/')}/notifications/payment-success"
        body = json.dumps({
            "appointment_id": appointment_id,
            "patient_id": payload.get("patient_id"),
            "transaction_id": payload.get("transaction_id"),
            "amount": payload.get("amount"),
            "currency": payload.get("currency"),
            "phone_number": payload.get("phone_number"),
            "patient_address": payload.get("patient_address"),
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        for attempt in range(1, MAX_HTTP_RETRIES + 1):
            response = self._http_post(notify_url, body, headers)
            status = response.get("status", 500)
            if 200 <= status < 300:
                self.logger.info("Notification API call completed successfully")
                return
            if 400 <= status < 500:
                raise FatalException(
                    f"Notification API returned {status} for appointment {appointment_id}: {response.get('body')}"
                )
            self.logger.warning(f"Notification API returned transient status {status}, retrying (attempt {attempt})")
            if attempt < MAX_HTTP_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)

        raise RetryableException("Failed to call Notification API after retries")

    def _http_post(self, url: str, body: bytes, headers: dict) -> dict:
        request_obj = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request_obj, timeout=HTTP_TIMEOUT) as resp:
                return {
                    "status": resp.getcode(),
                    "body": resp.read().decode("utf-8", errors="ignore"),
                }
        except urllib.error.HTTPError as http_err:
            body = http_err.read().decode("utf-8", errors="ignore")
            return {"status": http_err.code, "body": body}
        except urllib.error.URLError as url_err:
            raise RetryableException(f"Network error: {url_err}")


class RetryableException(Exception):
    pass


class FatalException(Exception):
    pass


if __name__ == "__main__":
    consumer = PaymentSuccessConsumer()
    consumer.run()
