from flask import Flask, request, jsonify, g
from flasgger import Swagger
from sqlalchemy import select
from werkzeug.exceptions import HTTPException
from app.models import Patient, Allergies
from app.database import engine, SessionLocal
from app import models
from app.error_publisher import publish_error
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
swagger = Swagger(app, template={
    "info": {
        "title": "Patient Microservice API",
        "version": "1.0.0",
        "description": "Check for patient allergies and get patient details"
    }
})

# create tables if not exist
SERVICE_NAME = "patient"
SERVICE_UP = Gauge("service_up", "1 if service is up, 0 otherwise", ["service_name"])
with app.app_context():
    models.Base.metadata.create_all(bind=engine)


def get_db():
    if 'db' not in g:
        g.db = SessionLocal()
    return g.db

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def _normalize_text(value):
  if value is None:
    return ""
  return " ".join(str(value).lower().split())


def _allergy_matches(prescription_item, allergy_item):
  prescription_norm = _normalize_text(prescription_item)
  allergy_norm = _normalize_text(allergy_item)
  if not prescription_norm or not allergy_norm:
    return False
  return allergy_norm in prescription_norm or prescription_norm in allergy_norm

def error_response(status_code, message, error_code, payload=None):
    publish_error(
        source_service="patient_service",
        error_code=error_code,
        error_message=message,
        payload=payload
    )
    return jsonify({"code": status_code, "message": message}), status_code

@app.errorhandler(Exception)
def handle_unexpected_error(err):
    if isinstance(err, HTTPException):
        return error_response(
            err.code or 500,
            err.description,
            f"PATIENT-{err.code or 500}-HTTP",
            {"path": request.path, "method": request.method},
        )
    return error_response(
        500,
        "Internal server error",
        "PATIENT-500-UNHANDLED",
        {"path": request.path, "method": request.method, "error": str(err)},
    )

@app.route("/patient/check-allergies", methods=['POST'])
def check_allergies():
    """
    Check patient allergies against prescribed drugs
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            patient_id:
              type: integer
              example: 1
            prescription:
              type: array
              items:
                type: string
              example: ["Aspirin", "Ibuprofen"]
    responses:
      200:
        description: Allergy check result
        schema:
          type: object
          properties:
            code:
              type: integer
            data:
              type: object
              properties:
                check:
                  type: string
                  enum: ["PASSED", "FAILED"]
                allergic_drugs:
                  type: array
                  items:
                    type: string
    """
    patient_id = request.json.get('patient_id')
    patient = get_db().scalar(
      select(Patient.patient_id).filter_by(patient_id=patient_id)
    )

    if not patient:
        return error_response(404, "Patient not found", "PATIENT-404-NOT_FOUND",
                              {"patient_id": patient_id})

    prescription_list = request.json.get('prescription', [])

    allergy_list = get_db().scalars(
        select(Allergies.allergy).filter_by(patient_id=patient_id)
    ).all()

    passed = True
    allergic_drugs = []

    for item in prescription_list:
      if any(_allergy_matches(item, allergy) for allergy in allergy_list):
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


@app.route("/patient/<int:patient_id>/details")
def find_by_id(patient_id):
    """
    Get patient details by ID
    ---
    parameters:
      - name: patient_id
        in: path
        type: integer
        required: true
        example: 1
    responses:
      200:
        description: Patient details retrieved successfully
        schema:
          type: object
          properties:
            code:
              type: integer
            data:
              type: object
      404:
        description: Patient not found
        schema:
          type: object
          properties:
            code:
              type: integer
            message:
              type: string
    """
    patient = get_db().scalar(
        select(Patient).filter_by(patient_id=patient_id)
    )

    if patient:
        return jsonify(
            {
                "code": 200,
                "data": patient.json()
            }
        )
    return error_response(404, "Patient not found.", "PATIENT-404-NOT_FOUND",
                          {"patient_id": patient_id})


@app.route("/patients", methods=['GET'])
def get_all_patients():
    """
    Get all patients.
    ---
    responses:
      200:
        description: List of patients
        schema:
          type: object
          properties:
            code:
              type: integer
            data:
              type: array
              items:
                type: object
      404:
        description: No patients found
    """
    patients = get_db().scalars(select(Patient).order_by(Patient.patient_id)).all()

    if not patients:
        return error_response(404, "No patients found.", "PATIENT-404-NOT_FOUND")

    return jsonify({
        "code": 200,
        "data": [patient.json() for patient in patients],
    })


@app.route("/patients/<int:patient_id>/allergies", methods=['GET'])
def get_patient_allergies(patient_id):
    """
    Get patient allergies
    ---
    parameters:
      - name: patient_id
        in: path
        type: integer
        required: true
        example: 1
    responses:
      200:
        description: List of patient allergies
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 200
            data:
              type: array
              items:
                type: object
                properties:
                  allergy:
                    type: string
                    example: "Penicillin"
      404:
        description: Patient not found
    """
    patient = get_db().scalar(
        select(Patient).filter_by(patient_id=patient_id)
    )

    if not patient:
        return error_response(404, "Patient not found", "PATIENT-404-NOT_FOUND",
                              {"patient_id": patient_id})

    allergies = get_db().scalars(
        select(Allergies.allergy).filter_by(patient_id=patient_id)
    ).all()

    return jsonify({
        "code": 200,
        "data": [{"allergy": a} for a in allergies]
    })

@app.route("/metrics")
def metrics():
    SERVICE_UP.labels(service_name=SERVICE_NAME).set(1)
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

if __name__ == '__main__':
    app.run(port=5003, debug=True)
