import json
from datetime import datetime
from os import environ
from time import sleep

import pika
from flask import Flask, g, jsonify, request
from sqlalchemy import Column, DateTime, Enum, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from werkzeug.exceptions import HTTPException

app = Flask(__name__)

DB_URL = environ.get("dbURL", "mysql+pymysql://root:root@localhost:3306/appointment_db")
AMQP_URL = environ.get("AMQP_URL", "amqp://guest:guest@rabbitmq:5672/")
SERVICE_NAME = "appointment"
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


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


from app.error_publisher import publish_error as publish_error


def error_response(status_code, message, error_code, payload=None):
    publish_error(error_code=error_code, error_message=message, payload=payload)
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

    return error_response(
        500,
        "Internal server error",
        "APPT-500-UNHANDLED",
        {"path": request.path, "method": request.method, "error": str(err)},
    )


@app.route("/appointments/<int:id>", methods=["GET"])
def get_appointment(id):
    db = get_db()
    appointment = db.get(Appointment, id)
    if not appointment:
        return error_response(404, "Appointment not found", "APPT-404-NOT_FOUND", {"appointment_id": id})

    return jsonify({"code": 200, "data": appointment.json()}), 200


@app.route("/appointments/patient/<int:patient_id>", methods=["GET"])
def get_appointments_by_patient(patient_id):
    db = get_db()
    appointments = db.query(Appointment).filter(Appointment.patient_id == patient_id).all()
    
    return jsonify({
        "code": 200,
        "data": [appointment.json() for appointment in appointments]
    }), 200


@app.route("/appointments", methods=["POST"])
def create_appointment():
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
    db = get_db()
    appointment = db.get(Appointment, id)
    if not appointment:
        return error_response(404, "Appointment not found", "APPT-404-NOT_FOUND", {"appointment_id": id})

    data = request.get_json()
    new_status = data.get("status") if data else None

    if not new_status:
        return error_response(400, "status is required", "APPT-400-MISSING_STATUS", {"appointment_id": id})

    if new_status not in APPOINTMENT_STATUSES:
        return error_response(
            400,
            f"Invalid status. Must be one of: {', '.join(APPOINTMENT_STATUSES)}",
            "APPT-400-INVALID_STATUS",
            {"appointment_id": id, "status": new_status},
        )

    appointment.status = new_status
    db.commit()
    db.refresh(appointment)

    return jsonify({"code": 200, "message": "Status updated successfully", "data": appointment.json()}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
