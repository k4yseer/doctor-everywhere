import resend
import os
from flask import Flask, jsonify, request
from dotenv import load_dotenv

load_dotenv()

resend.api_key = os.environ["RESEND_API_KEY"]

app = Flask(__name__)


@app.route("/notification/head-of-queue", methods=['POST'])
def head_of_queue():
    patient_email = request.json.get('email')
    meeting_link = request.json.get('meeting_link')
    params: resend.Emails.SendParams = {
        "from": "Doctor Everywhere <onboarding@resend.dev>",
        "to": [f"{patient_email}"],
        "subject": "You're at the front of the queue",
        "html": f"Click here to join the meeting: {meeting_link}",
    }

    r = resend.Emails.send(params)

    return jsonify(r)

@app.route("/notification/send-mc", methods=['POST'])
def send_mc():
    patient_email = request.form.get('email')
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
        "from": "Doctor Everywhere <onboarding@resend.dev>",
        "to": [f"{patient_email}"],
        "subject": "Medical Certificate",
        "html": "Attached is your MC.",
        "attachments": [attachment],
    }

    r = resend.Emails.send(params)

    return jsonify(r)


if __name__ == "__main__":
    app.run(port=5000, debug=True)