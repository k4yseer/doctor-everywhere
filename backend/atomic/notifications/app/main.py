from flask import Flask, jsonify, request
from flasgger import Swagger
from app import emails

app = Flask(__name__)
swagger = Swagger(app, template={
    "info": {
        "title": "Notifications Microservice API",
        "version": "1.0.0",
        "description": "Send email notifications to patients to join the consultation, get payment details and MC"
    }
})

is_valid_email = emails.is_valid_email

@app.route("/notification/head-of-queue", methods=['POST'])
def head_of_queue():
    """
    Notify patient at head of queue
    ---
    description: Send an email to the patient when they reach the head of queue with a meeting link.
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            email:
              type: string
              format: email
              example: "patient@example.com"
            meeting_link:
              type: string
              example: "https://meet.example.com/abc123"
    responses:
      200:
        description: Email sent successfully
        schema:
          type: object
          properties:
            code:
              type: integer
            message:
              type: string
            id:
              type: string
      400:
        description: Bad request (missing/invalid data)
        schema:
          type: object
          properties:
            error:
              type: string
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            code:
              type: integer
            message:
              type: string
    """
    patient_email = request.json.get('email')
    meeting_link = request.json.get('meeting_link')

    if meeting_link is None or patient_email is None:
        return jsonify({
            "error": "Missing required fields"
        }), 400

    if not is_valid_email(patient_email):
        return jsonify({
            "error": "Invalid email"
        }), 400

    try:
        r = emails.head_of_queue(patient_email, meeting_link)
        return jsonify({
            "code": 200,
            "message": "Email sent successfully",
            "id": r["id"]
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": str(e),
        }), 500

@app.route("/notification/send-mc", methods=['POST'])
def send_mc():
    """
    Send medical certificate to patient via email
    ---
    consumes:
      - multipart/form-data
    parameters:
      - name: email
        in: formData
        type: string
        format: email
        required: true
        example: "patient@example.com"
      - name: appointment_id
        in: formData
        type: string
        required: true
        example: "abc123"
      - name: file
        in: formData
        type: file
        required: true
        description: "PDF or image of medical certificate"
    responses:
      200:
        description: Email sent successfully
        schema:
          type: object
          properties:
            code:
              type: integer
            message:
              type: string
            id:
              type: string
      400:
        description: Bad request (missing/invalid data)
        schema:
          type: object
          properties:
            error:
              type: string
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            code:
              type: integer
            message:
              type: string
    """
    patient_email = request.form.get('email')
    appointment_id = request.form.get('appointment_id')
    mc = request.files.get("file")
    
    if appointment_id is None or mc is None or patient_email is None:
        return jsonify({
            "error": "Missing required fields"
        }), 400

    if not is_valid_email(patient_email):
        return jsonify({
            "error": "Invalid email"
        }), 400

    file_bytes = mc.read()
    filename = mc.filename

    try:
        r = emails.send_mc(patient_email, appointment_id, file_bytes, filename)
        return jsonify({
            "code": 200,
            "message": "Email sent successfully",
            "id": r["id"]
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": str(e),
        }), 500

@app.route("/notification/payment-details", methods=['POST'])
def payment_details():
    """
    Notify patient of payment status
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            email:
              type: string
              format: email
              example: "patient@example.com"
            appointment_id:
              type: string
              example: "abc123"
            is_successful:
              type: boolean
              example: true
    responses:
      200:
        description: Email sent successfully
        schema:
          type: object
          properties:
            code:
              type: integer
            message:
              type: string
            id:
              type: string
      400:
        description: Bad request (missing/invalid data)
        schema:
          type: object
          properties:
            error:
              type: string
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            code:
              type: integer
            message:
              type: string
    """
    patient_email = request.json.get('email')
    appointment_id = request.json.get('appointment_id')
    is_successful = request.json.get('is_successful')

    if appointment_id is None or is_successful is None or patient_email is None:
        return jsonify({
            "error": "Missing required fields"
        }), 400

    if not is_valid_email(patient_email):
        return jsonify({
            "error": "Invalid email"
        }), 400

    try:
        r = emails.payment_details(patient_email, appointment_id, is_successful)
        return jsonify({
            "code": 200,
            "message": "Email sent successfully",
            "id": r["id"]
        })
    except Exception as e:
        return jsonify({
            "code": 500,
            "message": str(e),
        }), 500


if __name__ == "__main__":
    app.run(port=5004, debug=True)