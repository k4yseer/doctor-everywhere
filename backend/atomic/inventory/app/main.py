from flask import Flask, request, jsonify, g
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Numeric
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from flasgger import Swagger, swag_from
from os import environ, path

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


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


# ── Reserve Medicine ────────────────────────────────────────────────────────
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
        return jsonify({"error": "Request body is required"}), 400

    medicine_code = data.get("medicine_code")
    appointment_id = data.get("appointment_id")
    amount = data.get("amount")

    if not medicine_code or not appointment_id or amount is None:
        return jsonify({"error": "medicine_code, appointment_id, and amount are required"}), 400

    if not isinstance(appointment_id, int) or appointment_id <= 0:
        return jsonify({"error": "appointment_id must be a positive integer"}), 400

    if not isinstance(amount, int) or amount <= 0:
        return jsonify({"error": "amount must be a positive integer"}), 400

    db = get_db()

    # Use row-level locking to avoid race conditions
    try:
        # Acquire FOR UPDATE lock on the medicine row
        medicine = db.query(Medicine).with_for_update().filter_by(medicine_code=medicine_code).first()
        if not medicine:
            return jsonify({"error": f"Medicine '{medicine_code}' not found"}), 404

        if medicine.stock_available < amount:
            return jsonify({
                "error": "Insufficient stock",
                "stock_available": medicine.stock_available,
                "requested": amount,
            }), 400

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
        return jsonify({"error": "Internal server error"}), 500
    

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
        return jsonify({"error": f"No reservations found for appointment_id '{appointment_id}'"}), 404

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
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=True)
