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
    meeting_link = request.json.get('meeting_link')

    if meeting_link is None or patient_email is None:
        return jsonify({
            "error": "Missing required fields"
        }), 400

    if not is_valid_email(patient_email):
        return jsonify({
            "error": "Invalid email"
        }), 400

    params: resend.Emails.SendParams = {
        "from": f"Doctor Everywhere <notifications@{domain}>",
        "to": [f"{patient_email}"],
        "subject": "Doctor Everywhere Consultation Link",
        "html": f"""
            <p>Dear Patient,<p>
            <p>Click here to join the consultation: {meeting_link}. Thank you for your patience.</p>
        """,
        "text": "Please click the link to join the consultation. "
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

    file_bytes: bytes = mc.read()
    filename: str = mc.filename

    attachment: resend.Attachment = {
        "content": list(file_bytes),  # Resend expects a list of ints
        "filename": filename,
    }

    params: resend.Emails.SendParams = {
        "from": f"Doctor Everywhere <notifications@{domain}>",
        "to": [f"{patient_email}"],
        "subject": f"Medical Certificate (Appointment #{appointment_id})",
        "html": f"""
            <p>Dear Patient,<p>
            <p>Attached is your MC for for Appointment <strong>#{appointment_id}</strong>.<p>
            <p>You may view your prescription and delivery details directly on the <strong>Doctor Everywhere</strong> app</p>
            <p>Warm regards, <br/><strong>Doctor Everywhere</strong></P>
        """,
        "text": f"""
            Attached is your MC for Appointment #{appointment_id}. 
            View your prescription and delivery details on the Doctor Everywhere app.
        """,
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

    subject = ""
    html = ""
    text = ""

    if is_successful:
        subject = f"Payment Received (Appointment #{appointment_id})"
        html = f"""
            <p>Dear Patient,<p>
            <p>We're writing to confirm that your payment for Appointment <strong>#{appointment_id}</strong>
            has been successfully processed.</p>
            <p>You may view your prescription and delivery details directly on the <strong>Doctor Everywhere</strong> app</p>
            <p>Warm regards, <br/><strong>Doctor Everywhere</strong></P>
        """
        text = f"""
            Your payment for Appointment #{appointment_id} was successful. 
            View your prescription and delivery details on the Doctor Everywhere app.
        """
    else:
        subject = f"Payment Unsuccessful (Appointment #{appointment_id})"
        html = f"""
            <p>Dear Patient,<p>
            <p>We were unable to process your payment for Appointment <strong>#{appointment_id}</strong></p>
            <p>Please open the <strong>Doctor Everywhere</strong> app to review your payment details and try again at your convenience.</p>
            <p>Warm regards, <br/><strong>Doctor Everywhere</strong></P>
        """
        text = f"""
            Your payment for Appointment #{appointment_id} was unsuccessful. 
            Please retry via Doctor Everywhere app.
        """

    params: resend.Emails.SendParams = {
        "from": f"Doctor Everywhere <notifications@{domain}>",
        "to": [f"{patient_email}"],
        "subject": subject,
        "html": html,
        "text": text
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