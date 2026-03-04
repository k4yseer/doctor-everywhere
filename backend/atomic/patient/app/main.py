from flask import Flask, request, jsonify
from sqlalchemy import select
from app.models import Patient, Allergies
from app.database import engine, SessionLocal

app = Flask(__name__)

from app import models

# create tables if not exist
@app.before_request
def init_db():
    try:
        models.Base.metadata.create_all(bind=engine)
    except Exception:
        pass

session = SessionLocal()

from app import seed
seed.register_cli(app)

@app.route("/patient/check-allergies", methods=['POST'])
def check_allergies():
    patient_id = request.json.get('patient_id')
    prescription_list = request.json.get('prescription', [])

    allergy_list = session.scalars(
        select(Allergies.allergy).filter_by(patient_id=patient_id)
    ).all()

    passed = True
    allergic_drugs = []

    for item in prescription_list:
        if item in allergy_list:
            passed = False
            allergic_drugs.append(item)
    
    if passed:
        return jsonify(
            {
                "code": 200, 
                "data": {
                    "check": "PASSED"
                }
            }
        )

    return jsonify(
        {
            "code": 200, 
            "data": {
                "check": "FAILED",
                "allergic_drugs": allergic_drugs
            }
        }
    )


@app.route("/patient/<string:patient_id>/details")
def find_by_id(patient_id):
    patient = session.scalar(
        select(Patient).filter_by(patient_id=patient_id)
    )

    if patient:
        return jsonify(
            {
                "code": 200,
                "data": patient.json()
            }
        )
    return jsonify(
        {
            "code": 404,
            "message": "Patient not found."
        }
    ), 404

if __name__ == '__main__':
    app.run(port=5000, debug=True)
