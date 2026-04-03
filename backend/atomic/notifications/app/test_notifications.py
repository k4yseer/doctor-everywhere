from notification_publisher import publish_notification

# Example 1: head-of-queue notification
publish_notification("head-of-queue", {
    "email": "copoci3248@agoalz.com",
    "meeting_link": "https://meet.example.com/test123"
})

# Example 2: no-show notification
publish_notification("no-show", {
    "email": "copoci3248@agoalz.com",
    "appointment_id": "appt-001"
})

# Example 3: payment-details
publish_notification("payment-details", {
    "email": "copoci3248@agoalz.com",
    "appointment_id": "appt-001",
    "is_successful": True
})

# Example 4: send-mc (base64 file)
import base64
file_content = base64.b64encode(b"Hello, PDF content").decode()
publish_notification("send-mc", {
    "email": "copoci3248@agoalz.com",
    "appointment_id": "appt-001",
    "filename": "invoice.pdf",
    "file_content": file_content
})