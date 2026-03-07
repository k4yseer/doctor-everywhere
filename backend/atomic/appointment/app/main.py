from flask import Flask, request, jsonify, g
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Enum, select
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from datetime import datetime
from os import environ

app = Flask(__name__)

DB_URL = environ.get('dbURL', 'mysql+pymysql://root:root@localhost:3306/appointment_db')
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# CONFIRMED  → appointment is booked (initial state)
# PENDING_PAYMENT → consultation completed, awaiting payment
# PAID        → payment received, appointment fully closed
APPOINTMENT_STATUSES = ('CONFIRMED', 'PENDING_PAYMENT', 'PAID')


class Base(DeclarativeBase):
    pass


class Appointment(Base):
    __tablename__ = 'appointments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, nullable=False)
    doctor_id = Column(Integer, nullable=False)
    slot_datetime = Column(DateTime, nullable=False)
    meet_link = Column(String(512), nullable=True)
    status = Column(
        Enum(*APPOINTMENT_STATUSES),
        nullable=False,
        default='CONFIRMED'
    )

    def json(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "slot_datetime": self.slot_datetime.isoformat(),
            "meet_link": self.meet_link,
            "status": self.status
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


@app.route("/appointments/<int:id>", methods=["GET"])
def get_appointment(id):
    """
    Retrieves a single appointment by ID.
    ---
    parameters:
      - name: id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Appointment details
        schema:
          type: object
          properties:
            code:
              type: integer
            data:
              type: object
              properties:
                id:
                  type: integer
                patient_id:
                  type: integer
                doctor_id:
                  type: integer
                slot_datetime:
                  type: string
                meet_link:
                  type: string
                status:
                  type: string
      404:
        description: Appointment not found
    """
    db = get_db()
    appointment = db.get(Appointment, id)
    if not appointment:
        return jsonify({"code": 404, "message": "Appointment not found"}), 404

    return jsonify({"code": 200, "data": appointment.json()}), 200


@app.route("/appointments", methods=["POST"])
def create_appointment():
    """
    Creates a new appointment with status PENDING_PAYMENT.
    ---
    parameters:
      - name: body
        in: body
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
              example: 2
            slot_datetime:
              type: string
              example: "2026-03-10T09:00:00"
            meet_link:
              type: string
              example: "https://meet.google.com/abc-defg-hij"
    responses:
      201:
        description: Appointment created
        schema:
          type: object
          properties:
            code:
              type: integer
            appointment_id:
              type: integer
            data:
              type: object
      400:
        description: Missing or invalid required fields
    """
    db = get_db()
    data = request.get_json()

    if not data:
        return jsonify({"code": 400, "message": "Request body is required"}), 400

    patient_id = data.get("patient_id")
    doctor_id = data.get("doctor_id")
    raw_dt = data.get("slot_datetime")

    if not all([patient_id, doctor_id, raw_dt]):
        return jsonify({"code": 400, "message": "patient_id, doctor_id, and slot_datetime are required"}), 400

    try:
        slot_dt = datetime.fromisoformat(raw_dt)
    except ValueError:
        return jsonify({"code": 400, "message": "Invalid slot_datetime format. Use ISO 8601."}), 400

    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=doctor_id,
        slot_datetime=slot_dt,
        meet_link=data.get("meet_link"),
        status='CONFIRMED'
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return jsonify({
        "code": 201,
        "appointment_id": appointment.id,
        "data": appointment.json()
    }), 201


@app.route("/appointments/<int:id>/status", methods=["PUT"])
def update_appointment_status(id):
    """
    Updates the status of an existing appointment.
    ---
    parameters:
      - name: id
        in: path
        type: integer
        required: true
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - status
          properties:
            status:
              type: string
              enum: ["CONFIRMED", "PENDING_PAYMENT", "PAID"]
              example: "PENDING_PAYMENT"
    responses:
      200:
        description: Status updated successfully
      400:
        description: Missing or invalid status
      404:
        description: Appointment not found
    """
    db = get_db()
    appointment = db.get(Appointment, id)
    if not appointment:
        return jsonify({"code": 404, "message": "Appointment not found"}), 404

    data = request.get_json()
    new_status = data.get("status") if data else None

    if not new_status:
        return jsonify({"code": 400, "message": "status is required"}), 400

    if new_status not in APPOINTMENT_STATUSES:
        return jsonify({
            "code": 400,
            "message": f"Invalid status. Must be one of: {', '.join(APPOINTMENT_STATUSES)}"
        }), 400

    appointment.status = new_status
    db.commit()
    db.refresh(appointment)

    return jsonify({"code": 200, "message": "Status updated successfully", "data": appointment.json()}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
