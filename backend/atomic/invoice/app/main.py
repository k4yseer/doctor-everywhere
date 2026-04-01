from flask import Flask, request, jsonify, g
from flasgger import Swagger
from sqlalchemy import create_engine, Column, String, Numeric, DateTime
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from datetime import datetime
from os import environ
import uuid

app = Flask(__name__)
Swagger(app, template={
    "info": {
        "title": "Invoice Service API",
        "version": "1.0.0",
        "description": "Manages invoices linked to patient appointments.",
    }
})

DB_URL = environ.get('dbURL', 'mysql+pymysql://root:root@localhost:3306/invoice_db')
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

class Invoice(Base):
    __tablename__ = 'invoices'

    invoice_id = Column(String(64), primary_key=True)
    appointment_id = Column(String(64), nullable=False)
    patient_id = Column(String(64), nullable=False)
    consultation_fee = Column(Numeric(10, 2), nullable=False, default=0.0)
    medicine_fee = Column(Numeric(10, 2), nullable=False, default=0.0)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(8), nullable=False)
    payment_status = Column(String(32), nullable=False)
    stripe_charge_id = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def json(self):
        return {
            'invoice_id': self.invoice_id,
            'appointment_id': self.appointment_id,
            'patient_id': self.patient_id,
            'consultation_fee': float(self.consultation_fee),
            'medicine_fee': float(self.medicine_fee),
            'amount': float(self.amount),
            'currency': self.currency,
            'payment_status': self.payment_status,
            'stripe_charge_id': self.stripe_charge_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
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


@app.route('/invoices/<string:appt_id>', methods=['GET'])
def get_invoice(appt_id):
    """
    Get invoice by appointment ID.
    ---
    tags:
      - Invoices
    parameters:
      - in: path
        name: appt_id
        type: string
        required: true
        example: "1"
    responses:
      200:
        description: Invoice details
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            data:
              $ref: '#/definitions/Invoice'
      404:
        description: Invoice not found
    definitions:
      Invoice:
        type: object
        properties:
          invoice_id:
            type: string
            example: "550e8400-e29b-41d4-a716-446655440000"
          appointment_id:
            type: string
            example: "1"
          patient_id:
            type: string
            example: "10000001"
          amount:
            type: number
            example: 50.00
          currency:
            type: string
            example: "sgd"
          payment_status:
            type: string
            example: "PAID"
          stripe_charge_id:
            type: string
            example: "ch_3NxWBz..."
          created_at:
            type: string
            format: date-time
    """
    db = get_db()
    invoice = db.query(Invoice).filter_by(appointment_id=appt_id).first()

    if not invoice:
        return jsonify({'code': 404, 'message': 'Invoice not found for appointment_id: ' + appt_id}), 404

    return jsonify({'code': 200, 'data': invoice.json()}), 200


@app.route('/invoices/<string:appt_id>', methods=['POST'])
def create_invoice(appt_id):
    """
    Create an invoice for an appointment.
    ---
    tags:
      - Invoices
    consumes:
      - application/json
    parameters:
      - in: path
        name: appt_id
        type: string
        required: true
        example: "1"
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - patient_id
            - amount
            - currency
            - payment_status
          properties:
            patient_id:
              type: string
              example: "10000001"
            amount:
              type: number
              example: 50.00
            currency:
              type: string
              example: "sgd"
            payment_status:
              type: string
              example: "PAID"
            stripe_charge_id:
              type: string
              example: "ch_3NxWBz..."
            invoice_id:
              type: string
              description: Optional — auto-generated if omitted
              example: "550e8400-e29b-41d4-a716-446655440000"
    responses:
      201:
        description: Invoice created
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 201
            data:
              $ref: '#/definitions/Invoice'
      400:
        description: Missing required fields
      409:
        description: Invoice already exists for this appointment
    """
    data = request.get_json()
    if not data:
        return jsonify({'code': 400, 'message': 'Request body is required'}), 400

    required = ['patient_id', 'currency', 'payment_status']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'code': 400, 'message': 'Missing required fields: ' + ', '.join(missing)}), 400

    consultation_fee = float(data.get('consultation_fee', 0.0))
    medicine_fee = float(data.get('medicine_fee', 0.0))
    if 'amount' in data and 'consultation_fee' not in data and 'medicine_fee' not in data:
        amount = float(data['amount'])
    else:
        amount = consultation_fee + medicine_fee

    db = get_db()
    exists = db.query(Invoice).filter_by(appointment_id=appt_id).first()
    if exists:
        return jsonify({'code': 409, 'message': 'Invoice already exists for appointment_id: ' + appt_id}), 409

    invoice = Invoice(
        invoice_id=data.get('invoice_id', str(uuid.uuid4())),
        appointment_id=appt_id,
        patient_id=data['patient_id'],
        consultation_fee=consultation_fee,
        medicine_fee=medicine_fee,
        amount=amount,
        currency=data['currency'],
        payment_status=data['payment_status'],
        stripe_charge_id=data.get('stripe_charge_id'),
        created_at=datetime.utcnow()
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    return jsonify({'code': 201, 'data': invoice.json()}), 201


@app.route('/invoices/<string:appt_id>', methods=['PUT'])
def update_invoice(appt_id):
    data = request.get_json()
    if not data:
        return jsonify({'code': 400, 'message': 'Request body is required'}), 400

    allowed = {'payment_status', 'stripe_charge_id'}
    update_data = {k: v for k, v in data.items() if k in allowed}
    if not update_data:
        return jsonify({'code': 400, 'message': 'Nothing to update'}), 400

    db = get_db()
    invoice = db.query(Invoice).filter_by(appointment_id=appt_id).first()
    if not invoice:
        return jsonify({'code': 404, 'message': 'Invoice not found for appointment_id: ' + appt_id}), 404

    if 'payment_status' in update_data:
        invoice.payment_status = update_data['payment_status']
    if 'stripe_charge_id' in update_data:
        invoice.stripe_charge_id = update_data['stripe_charge_id']

    db.commit()
    db.refresh(invoice)

    return jsonify({'code': 200, 'data': invoice.json()}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5008, debug=True)
