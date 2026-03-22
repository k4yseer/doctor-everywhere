import json
from os import environ

import pika
from flask import Flask, g, jsonify, request
from sqlalchemy import Column, Enum, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from werkzeug.exceptions import HTTPException

app = Flask(__name__)

DB_URL = environ.get("dbURL", "mysql+pymysql://root:root@localhost:3306/doctor_db")
AMQP_URL = environ.get("AMQP_URL", "amqp://guest:guest@rabbitmq:5672/")
SERVICE_NAME = "doctor"
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    specialty = Column(String(128), nullable=False)
    status = Column(Enum("AVAILABLE", "UNAVAILABLE"), nullable=False, default="AVAILABLE")

    def json(self):
        return {
            "id": self.id,
            "name": self.name,
            "specialty": self.specialty,
            "status": self.status,
        }


with app.app_context():
    Base.metadata.create_all(bind=engine)


def get_db():
    if "db" not in g:
        g.db = SessionLocal()
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


from app.error_publisher import publish_error as publish_error


def error_response(status_code, message, error_code, payload=None):
    publish_error(error_code=error_code, error_message=message, payload=payload)
    return jsonify({"code": status_code, "message": message}), status_code


@app.errorhandler(Exception)
def handle_unexpected_error(err):
    if isinstance(err, HTTPException):
        return error_response(
            err.code or 500,
            err.description,
            f"DOC-{err.code or 500}-HTTP",
            {"path": request.path, "method": request.method},
        )

    return error_response(
        500,
        "Internal server error",
        "DOC-500-UNHANDLED",
        {"path": request.path, "method": request.method, "error": str(err)},
    )


@app.route("/doctors", methods=["GET"])
def get_all_doctors():
    db = get_db()
    raw_status = request.args.get("status") or "available"
    requested_status = raw_status.upper()

    if requested_status not in {"AVAILABLE", "UNAVAILABLE"}:
        return error_response(
            400,
            "Invalid status. Must be AVAILABLE or UNAVAILABLE.",
            "DOC-400-INVALID_STATUS",
            {"status": raw_status},
        )

    query = select(Doctor).where(Doctor.status == requested_status)
    doctors = db.execute(query).scalars().all()
    return jsonify({"code": 200, "data": [d.json() for d in doctors]}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
