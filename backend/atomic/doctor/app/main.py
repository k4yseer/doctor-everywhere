from flask import Flask, request, jsonify, g
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Enum, ForeignKey, select
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from datetime import datetime
from os import environ

app = Flask(__name__)

DB_URL = environ.get('dbURL', 'mysql+pymysql://root:root@localhost:3306/doctor_db')
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class Doctor(Base):
    __tablename__ = 'doctors'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    specialty = Column(String(128), nullable=False)

    def json(self):
        return {
            "id": self.id,
            "name": self.name,
            "specialty": self.specialty
        }


class Availability(Base):
    __tablename__ = 'availability'

    id = Column(Integer, primary_key=True, autoincrement=True)
    doctor_id = Column(Integer, ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False)
    slot_datetime = Column(DateTime, nullable=False)
    status = Column(Enum('AVAILABLE', 'RESERVED'), nullable=False, default='AVAILABLE')

    def json(self):
        return {
            "id": self.id,
            "doctor_id": self.doctor_id,
            "slot_datetime": self.slot_datetime.isoformat(),
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


@app.route("/doctors", methods=["GET"])
def get_all_doctors():
    """
    Returns all doctors.
    ---
    responses:
      200:
        description: List of all doctors
        schema:
          type: object
          properties:
            code:
              type: integer
            data:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                  name:
                    type: string
                  specialty:
                    type: string
    """
    db = get_db()
    doctors = db.execute(select(Doctor)).scalars().all()
    return jsonify({"code": 200, "data": [d.json() for d in doctors]}), 200


@app.route("/doctors/<int:id>/availability", methods=["GET"])
def get_availability(id):
    """
    Returns all AVAILABLE slots for a given doctor.
    ---
    parameters:
      - name: id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: List of available slots
      404:
        description: Doctor not found
    """
    db = get_db()
    doctor = db.get(Doctor, id)
    if not doctor:
        return jsonify({"code": 404, "message": "Doctor not found"}), 404

    slots = db.execute(
        select(Availability).where(
            Availability.doctor_id == id,
            Availability.status == 'AVAILABLE'
        )
    ).scalars().all()

    return jsonify({"code": 200, "data": [s.json() for s in slots]}), 200


@app.route("/doctors/<int:id>/slot/reserve", methods=["PUT"])
def reserve_slot(id):
    """
    Reserves an AVAILABLE slot; returns 409 if already taken.
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
          properties:
            slot_datetime:
              type: string
              example: "2026-03-10T09:00:00"
    responses:
      200:
        description: Slot reserved successfully
      400:
        description: Missing slot_datetime
      404:
        description: Doctor not found
      409:
        description: Slot not available
    """
    db = get_db()
    doctor = db.get(Doctor, id)
    if not doctor:
        return jsonify({"code": 404, "message": "Doctor not found"}), 404

    data = request.get_json()
    raw_dt = data.get("slot_datetime") if data else None
    if not raw_dt:
        return jsonify({"code": 400, "message": "slot_datetime is required"}), 400

    try:
        slot_dt = datetime.fromisoformat(raw_dt)
    except ValueError:
        return jsonify({"code": 400, "message": "Invalid slot_datetime format. Use ISO 8601."}), 400

    slot = db.execute(
        select(Availability).where(
            Availability.doctor_id == id,
            Availability.slot_datetime == slot_dt,
            Availability.status == 'AVAILABLE'
        )
    ).scalars().first()

    if not slot:
        return jsonify({"code": 409, "message": "Slot is not available or does not exist"}), 409

    slot.status = 'RESERVED'
    db.commit()
    db.refresh(slot)
    return jsonify({"code": 200, "message": "Slot reserved successfully", "data": slot.json()}), 200


@app.route("/doctors/<int:id>/slot/release", methods=["PUT"])
def release_slot(id):
    """
    Releases a RESERVED slot back to AVAILABLE.
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
          properties:
            slot_datetime:
              type: string
              example: "2026-03-10T09:00:00"
    responses:
      200:
        description: Slot released successfully
      400:
        description: Missing slot_datetime
      404:
        description: Reserved slot not found
    """
    db = get_db()
    doctor = db.get(Doctor, id)
    if not doctor:
        return jsonify({"code": 404, "message": "Doctor not found"}), 404

    data = request.get_json()
    raw_dt = data.get("slot_datetime") if data else None
    if not raw_dt:
        return jsonify({"code": 400, "message": "slot_datetime is required"}), 400

    try:
        slot_dt = datetime.fromisoformat(raw_dt)
    except ValueError:
        return jsonify({"code": 400, "message": "Invalid slot_datetime format. Use ISO 8601."}), 400

    slot = db.execute(
        select(Availability).where(
            Availability.doctor_id == id,
            Availability.slot_datetime == slot_dt,
            Availability.status == 'RESERVED'
        )
    ).scalars().first()

    if not slot:
        return jsonify({"code": 404, "message": "No RESERVED slot found for the given datetime"}), 404

    slot.status = 'AVAILABLE'
    db.commit()
    db.refresh(slot)
    return jsonify({"code": 200, "message": "Slot released successfully", "data": slot.json()}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
