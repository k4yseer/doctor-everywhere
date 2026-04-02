import json
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import Column, DateTime, Enum, Integer, String, create_engine, delete
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]
SEED_PATH = BASE_DIR / "seed_scripts" / "common_seed.json"
DB_URL = os.environ.get("dbURL", "mysql+pymysql://root:root@localhost:3306/appointment_db")

Base = declarative_base()
engine = create_engine(DB_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

APPOINTMENT_STATUSES = ("CONFIRMED", "PENDING_PAYMENT", "PAID", "NO_SHOW")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, nullable=False)
    doctor_id = Column(Integer, nullable=False)
    slot_datetime = Column(DateTime, nullable=False)
    start_url = Column(String(512), nullable=True)
    join_url = Column(String(512), nullable=True)
    status = Column(Enum(*APPOINTMENT_STATUSES), nullable=False, default="CONFIRMED")


def load_seed_data():
    with open(SEED_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def seed():
    data = load_seed_data()

    Base.metadata.create_all(engine)

    with SessionLocal() as session:
        session.execute(delete(Appointment))
        session.commit()

        appointments = []
        for item in data["appointments"]:
            appointments.append(
                Appointment(
                    id=item["id"],
                    patient_id=item["patient_id"],
                    doctor_id=item["doctor_id"],
                    slot_datetime=datetime.fromisoformat(item["slot_datetime"]),
                    start_url=item["start_url"],
                    join_url=item["join_url"],
                    status=item["status"],
                )
            )

        session.add_all(appointments)
        session.commit()

    print(f"Seeded {len(appointments)} appointments into {DB_URL}")


if __name__ == "__main__":
    seed()
