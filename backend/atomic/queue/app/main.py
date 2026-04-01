from datetime import datetime, timezone
from os import environ

from flask import Flask, g, jsonify, request
from sqlalchemy import Column, DateTime, Integer, String, create_engine, func
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from werkzeug.exceptions import HTTPException
from flasgger import Swagger

from app.error_publisher import publish_error as _publish_error

app = Flask(__name__)
Swagger(app, template={
    "info": {
        "title": "Queue Service API",
        "version": "1.0.0",
        "description": "Atomic service for managing the patient consultation queue.",
    }
})

DB_URL = environ.get("dbURL", "mysql+pymysql://root:root@queue-db:3306/queue_db")
SERVICE_NAME = "queue"

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class QueueEntry(Base):
    __tablename__ = "queue_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def json(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


with app.app_context():
    Base.metadata.create_all(bind=engine)


# ── Helpers ──────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = SessionLocal()
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def error_response(status_code, message, error_code, payload=None):
    if status_code >= 500:
        _publish_error(source_service=SERVICE_NAME, error_code=error_code, error_message=message, payload=payload)
    return jsonify({"code": status_code, "message": message}), status_code


@app.errorhandler(Exception)
def handle_unexpected_error(err):
    app.logger.exception("Unhandled exception")
    if isinstance(err, HTTPException):
        return error_response(
            err.code or 500, err.description,
            f"QUEUE-{err.code or 500}-HTTP",
            {"path": request.path, "method": request.method},
        )
    return error_response(
        500, "Internal server error", "QUEUE-500-UNHANDLED",
        {"path": request.path, "method": request.method, "error": str(err)},
    )


# ── Routes ───────────────────────────────────────────────────────

@app.route("/queue", methods=["GET"])
def get_queue():
    """
    Get all patients currently in the queue.
    ---
    tags: [Queue]
    responses:
      200:
        description: List of queue entries ordered by arrival time
    """
    db = get_db()
    entries = db.query(QueueEntry).order_by(QueueEntry.created_at).all()
    return jsonify({"code": 200, "data": [e.json() for e in entries]}), 200


@app.route("/queue", methods=["POST"])
def create_queue_entry():
    """
    Add a patient to the queue.
    ---
    tags: [Queue]
    consumes: [application/json]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [patient_id]
          properties:
            patient_id:
              type: string
              example: "10000001"
    responses:
      201:
        description: Patient added to the queue
      400:
        description: Missing patient_id
      409:
        description: Patient already in queue
    """
    db = get_db()
    data = request.get_json()

    if not data:
        return error_response(400, "Request body is required", "QUEUE-400-MISSING_BODY")

    patient_id = data.get("patient_id")
    if not patient_id:
        return error_response(400, "patient_id is required", "QUEUE-400-MISSING_FIELDS")

    existing = db.query(QueueEntry).filter(QueueEntry.patient_id == patient_id).first()
    if existing:
        return error_response(409, "Patient is already in the queue", "QUEUE-409-DUPLICATE", {"patient_id": patient_id})

    entry = QueueEntry(patient_id=patient_id, created_at=datetime.now(timezone.utc))
    db.add(entry)
    db.commit()
    db.refresh(entry)

    queue_position = db.query(func.count(QueueEntry.id)).scalar()
    return jsonify({"code": 201, "queue_id": entry.id, "queue_position": queue_position, "data": entry.json()}), 201


@app.route("/queue/position/<string:patient_id>", methods=["GET"])
def get_queue_position(patient_id):
    """
    Get a patient's current position in the queue.
    ---
    tags: [Queue]
    parameters:
      - in: path
        name: patient_id
        type: string
        required: true
    responses:
      200:
        description: Queue position retrieved
      404:
        description: Patient not found in queue
    """
    db = get_db()
    entry = db.query(QueueEntry).filter(QueueEntry.patient_id == patient_id).first()
    if not entry:
        return error_response(404, "Patient not found in queue", "QUEUE-404-NOT_FOUND", {"patient_id": patient_id})
    position = db.query(func.count(QueueEntry.id)).filter(QueueEntry.created_at <= entry.created_at).scalar()
    return jsonify({"code": 200, "patient_id": patient_id, "queue_id": entry.id, "queue_position": position}), 200


@app.route("/queue/head", methods=["DELETE"])
def dequeue_head():
    """
    Remove and return the patient at the head of the queue.
    ---
    tags: [Queue]
    responses:
      200:
        description: Head of queue removed
      404:
        description: Queue is empty
    """
    db = get_db()
    entry = db.query(QueueEntry).order_by(QueueEntry.created_at).first()
    if not entry:
        return error_response(404, "Queue is empty", "QUEUE-404-EMPTY")
    patient_id = entry.patient_id
    db.delete(entry)
    db.commit()
    return jsonify({"code": 200, "patient_id": patient_id}), 200


@app.route("/queue/<int:entry_id>", methods=["DELETE"])
def remove_queue_entry(entry_id):
    """
    Remove a specific patient from the queue by entry ID.
    ---
    tags: [Queue]
    parameters:
      - in: path
        name: entry_id
        type: integer
        required: true
    responses:
      200:
        description: Queue entry removed
      404:
        description: Queue entry not found
    """
    db = get_db()
    entry = db.get(QueueEntry, entry_id)
    if not entry:
        return error_response(404, "Queue entry not found", "QUEUE-404-NOT_FOUND", {"entry_id": entry_id})
    db.delete(entry)
    db.commit()
    return jsonify({"code": 200, "message": "Queue entry removed"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5011, debug=True)
