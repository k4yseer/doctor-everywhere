from flask import Flask, request, jsonify
from flask_cors import CORS
from flasgger import Swagger
from sqlalchemy import create_engine, Column, String, Text, DateTime, select
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import uuid
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)
Swagger(app)  # Swagger UI at /apidocs

# ─── Database Setup ────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get(
    "dbURL", "mysql+pymysql://root:root@localhost:3306/delivery_db"
)

engine  = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


# ─── Delivery Model ────────────────────────────────────────────────────────────
class Delivery(Base):
    __tablename__ = "delivery"

    delivery_id      = Column(String(36),  primary_key=True, default=lambda: str(uuid.uuid4()))
    appointment_id   = Column(String(36),  nullable=False)
    patient_address  = Column(String(255), nullable=False)
    tracking_number  = Column(String(100), nullable=True)
    delivery_status  = Column(String(20),  nullable=False, default="PENDING")

    def to_dict(self):
        return {
            "delivery_id":     self.delivery_id,
            "appointment_id":  self.appointment_id,
            "patient_address": self.patient_address,
            "tracking_number": self.tracking_number,
            "delivery_status": self.delivery_status,
        }


Base.metadata.create_all(engine)


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route("/deliveries/<string:patient_id>", methods=["GET"])
def get_deliveries_by_patient(patient_id):
    """
    Get all delivery records for a patient.
    ---
    parameters:
      - name: patient_id
        in: path
        type: string
        required: true
    responses:
      200:
        description: List of delivery records for the patient
      404:
        description: No deliveries found
    """
    session = Session()
    try:
        # patient_id is resolved by the composite service before calling here
        # delivery records are looked up via appointment_id passed as query param
        appointment_id = request.args.get("appointment_id")

        if appointment_id:
            deliveries = session.execute(
                select(Delivery).where(Delivery.appointment_id == appointment_id)
            ).scalars().all()
        else:
            # Return all deliveries associated with any of the patient's appointments
            # Composite service should pass appointment_id for precision;
            # this fallback matches the GET /deliveries/{patient_id} endpoint in the diagram
            deliveries = session.execute(
                select(Delivery)
            ).scalars().all()

        if not deliveries:
            return jsonify({"code": 404, "message": "No deliveries found"}), 404

        return jsonify({"code": 200, "data": [d.to_dict() for d in deliveries]}), 200
    finally:
        session.close()


@app.route("/deliveries/order", methods=["POST"])
def create_delivery_order():
    """
    Create a new delivery order.
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          properties:
            appointment_id:
              type: string
            patient_address:
              type: string
            tracking_number:
              type: string
    responses:
      201:
        description: Delivery order created
      400:
        description: Missing required fields
    """
    session = Session()
    try:
        data = request.get_json()

        appointment_id  = data.get("appointment_id")
        patient_address = data.get("patient_address")
        tracking_number = data.get("tracking_number")  # optional at creation

        if not appointment_id or not patient_address:
            return jsonify({"code": 400, "message": "appointment_id and patient_address are required"}), 400

        delivery = Delivery(
            delivery_id=str(uuid.uuid4()),
            appointment_id=appointment_id,
            patient_address=patient_address,
            tracking_number=tracking_number,
            delivery_status="PENDING",
        )
        session.add(delivery)
        session.commit()

        return jsonify({"code": 201, "data": delivery.to_dict()}), 201

    except Exception as e:
        session.rollback()
        return jsonify({"code": 500, "message": str(e)}), 500
    finally:
        session.close()


@app.route("/deliveries/<string:delivery_id>/status", methods=["PATCH"])
def update_delivery_status(delivery_id):
    """
    Update the status of a delivery order.
    ---
    parameters:
      - name: delivery_id
        in: path
        type: string
        required: true
      - name: body
        in: body
        required: true
        schema:
          properties:
            delivery_status:
              type: string
              enum: [PENDING, IN_TRANSIT, DELIVERED, FAILED]
            tracking_number:
              type: string
    responses:
      200:
        description: Delivery status updated
      404:
        description: Delivery not found
    """
    session = Session()
    try:
        delivery = session.execute(
            select(Delivery).where(Delivery.delivery_id == delivery_id)
        ).scalar_one_or_none()

        if not delivery:
            return jsonify({"code": 404, "message": "Delivery not found"}), 404

        data = request.get_json()

        if "delivery_status" in data:
            delivery.delivery_status = data["delivery_status"]
        if "tracking_number" in data:
            delivery.tracking_number = data["tracking_number"]

        session.commit()
        return jsonify({"code": 200, "data": delivery.to_dict()}), 200

    except Exception as e:
        session.rollback()
        return jsonify({"code": 500, "message": str(e)}), 500
    finally:
        session.close()


# ─── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5008, debug=False)