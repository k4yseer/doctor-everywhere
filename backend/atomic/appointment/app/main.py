import json
from datetime import datetime
from os import environ
from time import sleep
import threading
import time

import pika
from flask import Flask, g, jsonify, request
from flasgger import Swagger
from sqlalchemy import Column, DateTime, Enum, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from werkzeug.exceptions import HTTPException
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
Swagger(app, template={
    "info": {
        "title": "Appointment Service API",
        "version": "1.0.0",
        "description": "Manages patient appointments, including creation and status updates.",
    }
})

DB_URL = environ.get("dbURL", "mysql+pymysql://root:root@localhost:3306/appointment_db")
AMQP_URL = environ.get("AMQP_URL", "amqp://guest:guest@rabbitmq:5672/")
SERVICE_NAME = "appointment"
EXCHANGE_NAME = "topic_logs"
PAYMENT_SUCCESS_ROUTING_KEY = "payment.success"
QUEUE_NAME = "appointment.payment.success"
SERVICE_UP = Gauge("service_up", "1 if service is up, 0 otherwise", ["service_name"])
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

APPOINTMENT_STATUSES = ("CONFIRMED", "PENDING_PAYMENT", "PAID", "NO_SHOW")


class Base(DeclarativeBase):
    pass


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, nullable=False)
    doctor_id = Column(Integer, nullable=False)
    slot_datetime = Column(DateTime, nullable=False)
    start_url = Column(String(512), nullable=True)
    join_url = Column(String(512), nullable=True)
    status = Column(Enum(*APPOINTMENT_STATUSES), nullable=False, default="CONFIRMED")
    clinical_notes = Column(String(5000), nullable=True)

    def json(self):
        slot = self.slot_datetime
        try:
            slot_val = slot.isoformat()
        except Exception:
            slot_val = str(slot) if slot is not None else None

        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "slot_datetime": slot_val,
            "start_url": self.start_url,
            "join_url": self.join_url,
            "status": self.status,
            "clinical_notes": self.clinical_notes,
        }


def init_db(max_attempts=20, wait_seconds=1):
    last_error = None
    for _ in range(max_attempts):
        try:
            with app.app_context():
                Base.metadata.create_all(bind=engine)
            return
        except Exception as err:
            last_error = err
            sleep(wait_seconds)

    if last_error:
        raise last_error


init_db()


def get_db():
    if "db" not in g:
        g.db = SessionLocal()
    return g.db


def process_payment_success(ch, method, properties, body):
    try:
        payload = json.loads(body)
        if payload.get("event_type") != "payment.success":
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        appointment_id = payload.get("appointment_id")
        if appointment_id is None:
            app.logger.warning("payment.success missing appointment_id")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        session = SessionLocal()
        try:
            appointment = session.get(Appointment, appointment_id)
            if not appointment:
                app.logger.warning(f"No appointment found for appointment_id={appointment_id}")
            elif appointment.status == "PAID":
                app.logger.info(f"Appointment {appointment_id} already PAID")
            else:
                appointment.status = "PAID"
                session.commit()
                app.logger.info(f"Appointment {appointment_id} marked as PAID")
        except Exception:
            app.logger.exception("Failed to update appointment status from payment.success event")
        finally:
            session.close()

        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception:
        app.logger.exception("Error processing payment.success message")
        ch.basic_ack(delivery_tag=method.delivery_tag)


def start_amqp_consumer():
    delay = 5
    while True:
        try:
            connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
            channel = connection.channel()
            channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
            channel.queue_declare(
                queue=QUEUE_NAME,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": EXCHANGE_NAME,
                    "x-dead-letter-routing-key": f"{QUEUE_NAME}.dlq",
                }
            )
            channel.queue_bind(
                exchange=EXCHANGE_NAME,
                queue=QUEUE_NAME,
                routing_key=PAYMENT_SUCCESS_ROUTING_KEY
            )
            channel.queue_declare(
                queue=f"{QUEUE_NAME}.dlq",
                durable=True
            )
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=process_payment_success)
            delay = 5
            channel.start_consuming()
        except Exception as err:
            publish_error(
                source_service=SERVICE_NAME,
                error_code="APPT-500-AMQP_CONSUMER",
                error_message=f"AMQP consumer failed: {err}",
                payload={"service": SERVICE_NAME},
            )
            time.sleep(delay)
            delay = min(delay * 2, 60)


from app.error_publisher import publish_error as publish_error

t = threading.Thread(target=start_amqp_consumer, daemon=True)
t.start()


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def error_response(status_code, message, error_code, payload=None):
    publish_error(source_service=SERVICE_NAME, error_code=error_code, error_message=message, payload=payload)
    return jsonify({"code": status_code, "message": message}), status_code


@app.errorhandler(Exception)
def handle_unexpected_error(err):
    if isinstance(err, HTTPException):
        return error_response(
            err.code or 500,
            err.description,
            f"APPT-{err.code or 500}-HTTP",
            {"path": request.path, "method": request.method},
        )

    import traceback
    app.logger.error(f"Unhandled Exception: {err}")
    app.logger.error(traceback.format_exc())

    return error_response(
        500,
        "Internal server error",
        "APPT-500-UNHANDLED",
        {"path": request.path, "method": request.method, "error": str(err)},
    )


@app.route("/appointments/<int:id>", methods=["GET"])
def get_appointment(id):
    """
    Get a single appointment by ID.
    ---
    tags:
      - Appointments
    parameters:
      - in: path
        name: id
        type: integer
        required: true
        example: 1
    responses:
      200:
        description: Appointment details
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            data:
              $ref: '#/definitions/Appointment'
      404:
        description: Appointment not found
    definitions:
      Appointment:
        type: object
        properties:
          id:
            type: integer
            example: 1
          patient_id:
            type: integer
            example: 1
          doctor_id:
            type: integer
            example: 1
          slot_datetime:
            type: string
            format: date-time
            example: "2026-04-01T10:00:00"
          start_url:
            type: string
            example: "https://zoom.us/s/123?zak=abc"
          join_url:
            type: string
            example: "https://zoom.us/j/123"
          status:
            type: string
            enum: [CONFIRMED, PENDING_PAYMENT, PAID, NO_SHOW]
            example: "CONFIRMED"
    """
    db = get_db()
    appointment = db.get(Appointment, id)
    if not appointment:
        return error_response(404, "Appointment not found", "APPT-404-NOT_FOUND", {"appointment_id": id})

    return jsonify({"code": 200, "data": appointment.json()}), 200


@app.route("/appointments/patient/<int:patient_id>", methods=["GET"])
def get_appointments_by_patient(patient_id):
    """
    Get all appointments for a specific patient.
    ---
    tags:
      - Appointments
    parameters:
      - in: path
        name: patient_id
        type: integer
        required: true
        example: 1
    responses:
      200:
        description: List of appointments for the patient
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            data:
              type: array
              items:
                $ref: '#/definitions/Appointment'
    """
    db = get_db()
    appointments = db.query(Appointment).filter(Appointment.patient_id == patient_id).all()
    
    return jsonify({
        "code": 200,
        "data": [appointment.json() for appointment in appointments]
    }), 200


@app.route("/appointments", methods=["POST"])
def create_appointment():
    """
    Create a new appointment.
    ---
    tags:
      - Appointments
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - patient_id
            - doctor_id
            - slot_datetime
          properties:
            patient_id:
              type: integer
              example: 1
            doctor_id:
              type: integer
              example: 1
            slot_datetime:
              type: string
              format: date-time
              example: "2026-04-01T10:00:00"
            start_url:
              type: string
              example: "https://zoom.us/s/123?zak=abc"
            join_url:
              type: string
              example: "https://zoom.us/j/123"
    responses:
      201:
        description: Appointment created successfully
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 201
            appointment_id:
              type: integer
              example: 5
            data:
              $ref: '#/definitions/Appointment'
      400:
        description: Missing or invalid fields
    """
    db = get_db()
    data = request.get_json()

    if not data:
        return error_response(400, "Request body is required", "APPT-400-MISSING_BODY")

    patient_id = data.get("patient_id")
    doctor_id = data.get("doctor_id")
    raw_dt = data.get("slot_datetime")

    if not all([patient_id, doctor_id, raw_dt]):
        return error_response(
            400,
            "patient_id, doctor_id, and slot_datetime are required",
            "APPT-400-MISSING_FIELDS",
            {"patient_id": patient_id, "doctor_id": doctor_id, "slot_datetime": raw_dt},
        )

    try:
        slot_dt = datetime.fromisoformat(raw_dt)
    except ValueError:
        return error_response(
            400,
            "Invalid slot_datetime format. Use ISO 8601.",
            "APPT-400-INVALID_DATETIME",
            {"slot_datetime": raw_dt},
        )

    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        slot_datetime=slot_dt,
        start_url=data.get("start_url"),
        join_url=data.get("join_url"),
        status="CONFIRMED",
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return jsonify({"code": 201, "appointment_id": appointment.id, "data": appointment.json()}), 201


@app.route("/appointments/<int:id>/status", methods=["PUT"])
def update_appointment_status(id):
    """
    Update appointment status and clinical notes.
    ---
    tags:
      - Appointment
    parameters:
      - in: path
        name: id
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            status:
              type: string
              example: "PENDING_PAYMENT"
            clinical_notes:
              type: string
              example: "Patient presents with persistent headache. Prescribed paracetamol."
    responses:
      200:
        description: Appointment updated successfully
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            message:
              type: string
              example: "Appointment updated successfully"
            data:
              $ref: '#/definitions/Appointment'
              $ref: '#/definitions/Appointment'
      400:
        description: Invalid or missing status
      404:
        description: Appointment not found
    """
    db = get_db()
    appointment = db.get(Appointment, id)
    if not appointment:
        return error_response(404, "Appointment not found", "APPT-404-NOT_FOUND", {"appointment_id": id})

    data = request.get_json() or {}
    new_status = data.get("status", "PENDING_PAYMENT")
    clinical_notes = data.get("clinical_notes")

    if new_status not in APPOINTMENT_STATUSES:
        return error_response(
            400,
            f"Invalid status. Must be one of: {', '.join(APPOINTMENT_STATUSES)}",
            "APPT-400-INVALID_STATUS",
            {"appointment_id": id, "status": new_status},
        )

    appointment.status = new_status
    if clinical_notes is not None:
        appointment.clinical_notes = clinical_notes
    db.commit()
    db.refresh(appointment)

    return jsonify({"code": 200, "message": "Appointment updated successfully", "data": appointment.json()}), 200

@app.route("/metrics")
def metrics():
    SERVICE_UP.labels(service_name=SERVICE_NAME).set(1)
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
