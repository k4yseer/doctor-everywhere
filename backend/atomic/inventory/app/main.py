from flask import Flask, request, jsonify, g
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Numeric
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from werkzeug.exceptions import HTTPException
from flasgger import Swagger, swag_from
from os import environ, path
import threading
import time
import pika
import json

from app.error_publisher import publish_error as _publish_error

app = Flask(__name__)

swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
}

swagger_template = {
    "info": {
        "title": "Inventory Service API",
        "description": "Manages medicine stock and medicine reservations.",
        "version": "1.0.0",
    },
    "basePath": "/",
}

Swagger(app, config=swagger_config, template=swagger_template)
SWAGGER_DIR = path.join(path.dirname(__file__), "swagger")

DB_URL = environ.get('dbURL', 'mysql+pymysql://root:root@localhost:3306/inventory_db')
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

AMQP_URL = environ.get('AMQP_URL', 'amqp://guest:guest@rabbitmq:5672/')
EXCHANGE_NAME = 'topic_logs'
PAYMENT_SUCCESS_ROUTING_KEY = 'payment.success'
QUEUE_NAME = 'inventory.payment.success'


class Base(DeclarativeBase):
    pass


class Medicine(Base):
    __tablename__ = 'medicine'

    medicine_code    = Column(String(50),  primary_key=True)
    medicine_name    = Column(String(255), nullable=False)
    stock_available  = Column(Integer,     nullable=False, default=0)
    unit_price       = Column(Numeric(10, 2), nullable=False, default=0)

    def json(self):
        return {
            "medicine_code":    self.medicine_code,
            "medicine_name":    self.medicine_name,
            "stock_available":  self.stock_available,
            "unit_price":       float(self.unit_price),
        }


class Reservation(Base):
    __tablename__ = 'reservations'

    reservation_id = Column(Integer,    primary_key=True, autoincrement=True)
    medicine_code  = Column(String(50), ForeignKey('medicine.medicine_code'), nullable=False)
    appointment_id = Column("appointment_id", Integer, nullable=False)
    amount         = Column(Integer,    nullable=False)

    def json(self):
        return {
            "reservation_id": self.reservation_id,
            "medicine_code":  self.medicine_code,
            "appointment_id": self.appointment_id,
            "amount":         self.amount,
        }


with app.app_context():
    Base.metadata.create_all(bind=engine)


def get_db():
    if 'db' not in g:
        g.db = SessionLocal()
    return g.db


def _fulfill_reservations_by_appointment(db, appointment_id):
    reservations = db.query(Reservation).filter_by(appointment_id=appointment_id).all()
    if not reservations:
        return {
            "fulfilled_reservations": [],
            "fulfilled_count": 0,
            "medicine_codes": [],
        }

    fulfilled_reservations = []
    medicine_codes = set()
    for reservation in reservations:
        db.query(Medicine).with_for_update().filter_by(medicine_code=reservation.medicine_code).first()
        medicine_codes.add(reservation.medicine_code)
        fulfilled_reservations.append(reservation.json())
        db.delete(reservation)

    db.commit()
    return {
        "fulfilled_reservations": fulfilled_reservations,
        "fulfilled_count": len(fulfilled_reservations),
        "medicine_codes": sorted(medicine_codes),
    }


@app.route("/inventory/<string:medicine_code>", methods=["GET"])
def get_medicine(medicine_code):
    db = get_db()
    medicine = db.query(Medicine).filter_by(medicine_code=medicine_code).first()
    if not medicine:
        return _error_response(
            404,
            f"Medicine '{medicine_code}' not found in inventory",
            "INVENTORY-404-NOT_FOUND",
            {"medicine_code": medicine_code},
        )
    return jsonify({"data": medicine.json()}), 200


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def _error_response(status_code, message, error_code, payload=None, publish=False):
    if status_code >= 400 or publish:
        _publish_error(
            source_service="inventory_service",
            error_code=error_code,
            error_message=message,
            payload=payload or {},
        )
    return jsonify({"error": message}), status_code


@app.errorhandler(Exception)
def handle_unexpected_error(err):
    if isinstance(err, HTTPException):
        return _error_response(
            err.code or 500,
            err.description,
            f"INVENTORY-{err.code or 500}-HTTP",
            {"path": request.path, "method": request.method},
            publish=False,
        )

    return _error_response(
        500,
        "Internal server error",
        "INVENTORY-500-UNHANDLED",
        {"path": request.path, "method": request.method, "error": str(err)},
        publish=True,
    )


# ── Get Medicines ────────────────────────────────────────────────────────
@app.route("/inventory/medicines", methods=["GET"])
@app.route("/inventory/medicines/", methods=["GET"])
@swag_from(path.join(SWAGGER_DIR, "get_medicines.yml"))
def get_medicines():
    """Get all medicines."""
    db = get_db()
    medicines = db.query(Medicine).all()
    return jsonify([medicine.json() for medicine in medicines]), 200


@app.route("/inventory/reservations/", methods=["GET"])
@swag_from(path.join(SWAGGER_DIR, "get_reservations.yml"))
def get_reservations():
    """Get all reservations."""
    db = get_db()
    reservations = db.query(Reservation).all()
    return jsonify([reservation.json() for reservation in reservations]), 200


@app.route("/inventory/reservations/appointment/<int:appointment_id>", methods=["GET"])
@swag_from(path.join(SWAGGER_DIR, "get_reservations_by_appointment.yml"))
def get_reservations_by_appointment(appointment_id):
    """Get reservations by appointment id."""
    db = get_db()
    reservations = db.query(Reservation).filter_by(appointment_id=appointment_id).all()
    return jsonify([reservation.json() for reservation in reservations]), 200


# ── Reserve Medicine ────────────────────────────────────────────────────────
@app.route("/inventory/reservations/", methods=["POST"])
@swag_from(path.join(SWAGGER_DIR, "reserve_medicine.yml"))
def reserve_medicine():
    """
        Reserve medicine for an appointment.
    """
    data = request.get_json()
    if not data:
        return _error_response(
            400,
            "Request body is required",
            "INVENTORY-400-MISSING_BODY",
        )

    medicine_code = data.get("medicine_code")
    appointment_id = data.get("appointment_id")
    amount = data.get("amount")

    if not medicine_code or not appointment_id or amount is None:
        return _error_response(
            400,
            "medicine_code, appointment_id, and amount are required",
            "INVENTORY-400-MISSING_FIELDS",
        )

    if not isinstance(appointment_id, int) or appointment_id <= 0:
        return _error_response(
            400,
            "appointment_id must be a positive integer",
            "INVENTORY-400-INVALID_APPOINTMENT_ID",
        )

    if not isinstance(amount, int) or amount <= 0:
        return _error_response(
            400,
            "amount must be a positive integer",
            "INVENTORY-400-INVALID_AMOUNT",
        )

    db = get_db()

    # Use row-level locking to avoid race conditions
    try:
        # Acquire FOR UPDATE lock on the medicine row
        medicine = db.query(Medicine).with_for_update().filter_by(medicine_code=medicine_code).first()
        if not medicine:
            return _error_response(
                404,
                f"Medicine '{medicine_code}' not found",
                "INVENTORY-404-MEDICINE_NOT_FOUND",
                {"medicine_code": medicine_code},
            )

        if medicine.stock_available < amount:
            return _error_response(
                400,
                "Insufficient stock",
                "INVENTORY-400-INSUFFICIENT_STOCK",
                {
                    "medicine_code": medicine_code,
                    "stock_available": medicine.stock_available,
                    "requested": amount,
                },
            )

        # Deduct from available and create reservation (reservations are source of truth)
        medicine.stock_available -= amount

        reservation = Reservation(
            medicine_code=medicine_code,
            appointment_id=appointment_id,
            amount=amount,
        )
        db.add(reservation)
        db.commit()
        db.refresh(reservation)

        return jsonify({
            "message": "Reservation created successfully",
            "reservation": reservation.json(),
            "medicine": medicine.json(),
        }), 201
    except Exception:
        db.rollback()
        app.logger.exception("reserve_medicine failed")
        return _error_response(
            500,
            "Internal server error",
            "INVENTORY-500-RESERVE_FAILED",
            {
                "path": request.path,
                "method": request.method,
                "medicine_code": medicine_code,
                "appointment_id": appointment_id,
                "amount": amount,
            },
            publish=True,
        )
    

# ── Fulfill Reserved Order ──────────────────────────────────────────────────
@app.route("/inventory/reservations/appointment/<int:appointment_id>/fulfill", methods=["POST"])
@swag_from(path.join(SWAGGER_DIR, "fulfill_reservation.yml"))
def fulfill_reservation(appointment_id):
    """
        Fulfill reservations by appointment id.
    """
    db = get_db()

    reservations = db.query(Reservation).filter_by(appointment_id=appointment_id).all()
    if not reservations:
        return _error_response(
            404,
            f"No reservations found for appointment_id '{appointment_id}'",
            "INVENTORY-404-NO_RESERVATIONS",
            {"appointment_id": appointment_id},
        )

    try:
        fulfilled_reservations = []
        medicine_codes = set()

        # Delete all reservations for an appointment; do not restore stock.
        for reservation in reservations:
            db.query(Medicine).with_for_update().filter_by(medicine_code=reservation.medicine_code).first()
            medicine_codes.add(reservation.medicine_code)
            fulfilled_reservations.append(reservation.json())
            db.delete(reservation)

        db.commit()

        return jsonify({
            "message": "Reservations fulfilled successfully",
            "appointment_id": appointment_id,
            "fulfilled_reservations": fulfilled_reservations,
            "fulfilled_count": len(fulfilled_reservations),
            "medicine_codes": sorted(medicine_codes),
        }), 200
    except Exception:
        db.rollback()
        return _error_response(
            500,
            "Internal server error",
            "INVENTORY-500-FULFILL_FAILED",
            {
                "path": request.path,
                "method": request.method,
                "appointment_id": appointment_id,
            },
            publish=True,
        )


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
            result = _fulfill_reservations_by_appointment(session, appointment_id)
            if result["fulfilled_count"] == 0:
                app.logger.info(f"No reservations to fulfill for appointment_id={appointment_id}")
            else:
                app.logger.info(
                    f"Fulfilled {result['fulfilled_count']} reservation(s) for appointment_id={appointment_id}"
                )
        except Exception:
            app.logger.exception("Failed to fulfill inventory reservations from payment.success event")
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
            channel.start_consuming()
        except Exception:
            app.logger.exception("Inventory service AMQP consumer error")
            time.sleep(delay)
            delay = min(delay * 2, 60)


t = threading.Thread(target=start_amqp_consumer, daemon=True)
t.start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5009, debug=True)
