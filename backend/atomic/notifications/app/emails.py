import resend
import os
import re
from dotenv import load_dotenv

load_dotenv()
resend.api_key = os.environ.get("RESEND_API_KEY")
domain = os.environ.get("DOMAIN_NAME")


def is_valid_email(email):
    return re.match(
        r"^(?!\.)(?!.*\.\.)([a-z0-9_'+\-\.]*)[a-z0-9_'+\-]@([a-z0-9][a-z0-9\-]*\.)+[a-z]{2,}$",
        email,
        re.IGNORECASE,
    )

def head_of_queue(patient_email, meeting_link):
    params: resend.Emails.SendParams = {
        "from": f"Doctor Everywhere <notifications@{domain}>",
        "to": [patient_email],
        "subject": "Doctor Everywhere Consultation Link",
        "html": f"""
            <p>Dear Patient,<p>
            <p>Click here to join the consultation: {meeting_link}. Thank you for your patience.</p>
            <p>Warm regards, <br/><strong>Doctor Everywhere</strong></P>
        """,
        "text": "Please click the link to join the consultation.",
    }
    return resend.Emails.send(params)


def send_mc(patient_email, appointment_id, file_bytes, filename):
    attachment: resend.Attachment = {
        "content": list(file_bytes),
        "filename": filename,
    }
    params: resend.Emails.SendParams = {
        "from": f"Doctor Everywhere <notifications@{domain}>",
        "to": [patient_email],
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
    return resend.Emails.send(params)


def payment_details(patient_email, appointment_id, is_successful):
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
        "to": [patient_email],
        "subject": subject,
        "html": html,
        "text": text,
    }
    return resend.Emails.send(params)
