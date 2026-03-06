import resend
import os
from flask import Flask, jsonify, request
from dotenv import load_dotenv
import re

load_dotenv()

resend.api_key = os.environ["RESEND_API_KEY"]
domain = os.environ["DOMAIN_NAME"]

app = Flask(__name__)

def is_valid_email(email):
    return re.match(r"^(?!\.)(?!.*\.\.)([a-z0-9_'+\-\.]*)[a-z0-9_'+\-]@([a-z0-9][a-z0-9\-]*\.)+[a-z]{2,}$", email, re.IGNORECASE)

@app.route("/notification/head-of-queue", methods=['POST'])
def head_of_queue():
    patient_email = request.json.get('email')
    if not is_valid_email(patient_email):
        return jsonify({
            "error": "Invalid email"
        }), 400

    meeting_link = request.json.get('meeting_link')
    params: resend.Emails.SendParams = {
        "from": f"Doctor Everywhere <notifications@{domain}>",
        "to": [f"{patient_email}"],
        "subject": "You're at the front of the queue",
        "html": f"Click here to join the meeting: {meeting_link}",
    }

    try:
        r = resend.Emails.send(params)
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
    patient_email = request.form.get('email')
    if not is_valid_email(patient_email):
        return jsonify({
            "error": "Invalid email"
        }), 400

    mc = request.files.get("file")
    if not mc:
        return jsonify({
            "error": "No file provided"
        }), 400

    file_bytes: bytes = mc.read()
    filename: str = mc.filename

    attachment: resend.Attachment = {
        "content": list(file_bytes),  # Resend expects a list of ints
        "filename": filename,
    }

    params: resend.Emails.SendParams = {
        "from": f"Doctor Everywhere <notifications@{domain}>",
        "to": [f"{patient_email}"],
        "subject": "Medical Certificate",
        "html": "Attached is your MC.",
        "attachments": [attachment],
    }

    try:
        r = resend.Emails.send(params)
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
    patient_email = request.json.get('email')
    if not is_valid_email(patient_email):
        return jsonify({
            "error": "Invalid email"
        }), 400

    appointment_id = request.json.get('appointment_id')
    is_successful = request.json.get('is_successful')

    params: resend.Emails.SendParams = {
        "from": f"Doctor Everywhere <notifications@{domain}>",
        "to": [f"{patient_email}"],
        "subject": f"Appointment {appointment_id} Payment Confirmation",
        "html": f"Your payment has been {'successful. You may view your prescription/delivery details on the app.' if is_successful 
                else 'unsuccessful. Please try again.'}",
    }

    try:
        r = resend.Emails.send(params)
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
    app.run(port=5000, debug=True)