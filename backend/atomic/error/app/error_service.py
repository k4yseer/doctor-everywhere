from flask import Flask, jsonify, request
from flask_cors import CORS
from flasgger import Swagger
from sqlalchemy import create_engine, Column, String, Text, DateTime, select
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import pika
import json
import uuid
import os
import threading
import time
from datetime import datetime

app = Flask(__name__)
CORS(app)
Swagger(app)  # Swagger UI available at /apidocs

# ─── Database Setup (plain SQLAlchemy, matching group style) ───────────────────
DATABASE_URL = os.environ.get(
    "dbURL", "mysql+pymysql://root:root@localhost:3306/error_db"
)

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


# ─── Error Model ───────────────────────────────────────────────────────────────
class Error(Base):
    __tablename__ = "error"

    error_id          = Column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp         = Column(DateTime,    nullable=False,   default=datetime.utcnow)
    source_service    = Column(String(100), nullable=False)
    error_code        = Column(String(50),  nullable=False)
    error_message     = Column(Text,        nullable=False)
    payload           = Column(Text,        nullable=True)   # JSON stored as TEXT
    resolution_status = Column(String(20),  nullable=False,  default="UNRESOLVED")

    def to_dict(self):
        return {
            "error_id":          self.error_id,
            "timestamp":         self.timestamp.isoformat(),
            "source_service":    self.source_service,
            "error_code":        self.error_code,
            "error_message":     self.error_message,
            "payload":           self.payload,
            "resolution_status": self.resolution_status,
        }


# Create tables if they don't exist
Base.metadata.create_all(engine)


# ─── AMQP Consumer ─────────────────────────────────────────────────────────────
AMQP_URL      = os.environ.get("AMQP_URL", "amqp://guest:guest@localhost:5672/")
EXCHANGE_NAME = "topic_logs"
ROUTING_KEY   = "*.error"   # catches appointment.error, doctor.error, patient.error, etc.


def process_error_message(ch, method, properties, body):
    """
    Callback triggered for every AMQP message matching *.error.
    Expected JSON body:
    {
        "source_service": "appointment_service",
        "error_code":     "APPT-500",
        "error_message":  "Failed to create appointment record",
        "payload":        { ...optional original request data... }
    }
    """
    try:
        data = json.loads(body)

        source_service = data.get("source_service", method.routing_key.split(".")[0])
        error_code     = data.get("error_code", "UNKNOWN")
        error_message  = data.get("error_message", "No message provided")
        payload        = json.dumps(data.get("payload")) if data.get("payload") else None

        session = Session()
        try:
            error_record = Error(
                error_id=str(uuid.uuid4()),
                source_service=source_service,
                error_code=error_code,
                error_message=error_message,
                payload=payload,
                resolution_status="UNRESOLVED",
            )
            session.add(error_record)
            session.commit()
            print(f"[ERROR SERVICE] Logged — {source_service} | {error_code} | {error_message}")
        except Exception as db_err:
            session.rollback()
            print(f"[ERROR SERVICE] DB write failed: {db_err}")
        finally:
            session.close()

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"[ERROR SERVICE] Failed to process AMQP message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_amqp_consumer():
    """Start RabbitMQ consumer in a background daemon thread with retry/backoff."""
    retry_delay_seconds = 2
    max_retry_delay_seconds = 30

    while True:
        connection = None
        try:
            connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
            channel = connection.channel()

            channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)

            result = channel.queue_declare(queue="error_queue", durable=True)
            queue_name = result.method.queue

            channel.queue_bind(exchange=EXCHANGE_NAME, queue=queue_name, routing_key=ROUTING_KEY)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=queue_name, on_message_callback=process_error_message)

            print(f"[ERROR SERVICE] Listening on exchange '{EXCHANGE_NAME}' | routing key '{ROUTING_KEY}'")
            # Reset retry delay after a successful setup.
            retry_delay_seconds = 2
            channel.start_consuming()

        except Exception as e:
            print(f"[ERROR SERVICE] AMQP connection/consumer failed: {e}. Retrying in {retry_delay_seconds}s...")
            time.sleep(retry_delay_seconds)
            retry_delay_seconds = min(max_retry_delay_seconds, retry_delay_seconds * 2)

        finally:
            try:
                if connection and connection.is_open:
                    connection.close()
            except Exception:
                pass


# ─── REST Endpoints ────────────────────────────────────────────────────────────
@app.route("/errors", methods=["GET"])
def get_all_errors():
    """
    Get all error records.
    ---
    responses:
      200:
        description: List of all error records
    """
    session = Session()
    try:
        errors = session.execute(select(Error).order_by(Error.timestamp.desc())).scalars().all()
        return jsonify({"code": 200, "data": [e.to_dict() for e in errors]}), 200
    finally:
        session.close()


@app.route("/errors/<string:error_id>", methods=["GET"])
def get_error(error_id):
    """
    Get a single error record by ID.
    ---
    parameters:
      - name: error_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: Error record found
      404:
        description: Error record not found
    """
    session = Session()
    try:
        error = session.execute(select(Error).where(Error.error_id == error_id)).scalar_one_or_none()
        if not error:
            return jsonify({"code": 404, "message": "Error record not found"}), 404
        return jsonify({"code": 200, "data": error.to_dict()}), 200
    finally:
        session.close()


@app.route("/errors/<string:error_id>/resolve", methods=["PATCH"])
def resolve_error(error_id):
    """
    Mark an error record as RESOLVED.
    ---
    parameters:
      - name: error_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: Error marked as resolved
      404:
        description: Error record not found
    """
    session = Session()
    try:
        error = session.execute(select(Error).where(Error.error_id == error_id)).scalar_one_or_none()
        if not error:
            return jsonify({"code": 404, "message": "Error record not found"}), 404
        error.resolution_status = "RESOLVED"
        session.commit()
        return jsonify({"code": 200, "data": error.to_dict()}), 200
    except Exception as e:
        session.rollback()
        return jsonify({"code": 500, "message": str(e)}), 500
    finally:
        session.close()


# ─── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    consumer_thread = threading.Thread(target=start_amqp_consumer, daemon=True)
    consumer_thread.start()

    app.run(host="0.0.0.0", port=5007, debug=False)
