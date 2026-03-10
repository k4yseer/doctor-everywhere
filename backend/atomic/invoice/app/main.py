from flask import Flask, request, jsonify, g
from sqlalchemy import create_engine, Column, String, Numeric, DateTime
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from datetime import datetime
from os import environ
import uuid

app = Flask(__name__)

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
    db = get_db()
    invoice = db.query(Invoice).filter_by(appointment_id=appt_id).first()

    if not invoice:
        return jsonify({'code': 404, 'message': 'Invoice not found for appointment_id: ' + appt_id}), 404

    return jsonify({'code': 200, 'data': invoice.json()}), 200


@app.route('/invoices/<string:appt_id>', methods=['POST'])
def create_invoice(appt_id):
    data = request.get_json()
    if not data:
        return jsonify({'code': 400, 'message': 'Request body is required'}), 400

    required = ['patient_id', 'amount', 'currency', 'payment_status']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'code': 400, 'message': 'Missing required fields: ' + ', '.join(missing)}), 400

    db = get_db()
    exists = db.query(Invoice).filter_by(appointment_id=appt_id).first()
    if exists:
        return jsonify({'code': 409, 'message': 'Invoice already exists for appointment_id: ' + appt_id}), 409

    invoice = Invoice(
        invoice_id=data.get('invoice_id', str(uuid.uuid4())),
        appointment_id=appt_id,
        patient_id=data['patient_id'],
        amount=data['amount'],
        currency=data['currency'],
        payment_status=data['payment_status'],
        stripe_charge_id=data.get('stripe_charge_id'),
        created_at=datetime.utcnow()
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    return jsonify({'code': 201, 'data': invoice.json()}), 201


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=True)
