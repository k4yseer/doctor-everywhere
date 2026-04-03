import json
import os
from datetime import date
from pathlib import Path

from sqlalchemy import Column, Date, ForeignKey, String, create_engine, delete
from sqlalchemy.orm import declarative_base, sessionmaker

# Paths and DB URL
BASE_DIR = Path(__file__).resolve().parents[1]
SEED_PATH = BASE_DIR / "seed_scripts" / "common_seed.json"

DB_URL = os.environ.get("dbURL")
if not DB_URL:
    DB_SERVER = os.environ.get("DB_SERVER", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "3306")
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "root")
    DATABASE = os.environ.get("DATABASE", "patient_db")
    DB_URL = (
        f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}:{DB_PORT}/{DATABASE}"
    )

# SQLAlchemy setup
Base = declarative_base()
engine = create_engine(DB_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

# Models
class Patient(Base):
    __tablename__ = "patients"

    patient_id = Column(String(8), primary_key=True)
    patient_name = Column(String(64), nullable=False)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(10), nullable=True)
    address = Column(String(64), nullable=False)
    contact_number = Column(String(8), nullable=False)
    email = Column(String(64), nullable=False)


class Allergy(Base):
    __tablename__ = "allergies"

    patient_id = Column(
        ForeignKey("patients.patient_id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    allergy = Column(String(64), primary_key=True)


# Load JSON
def load_seed_data():
    with open(SEED_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


# Seed function
def seed():
    data = load_seed_data()

    # Create tables if not exist
    Base.metadata.create_all(engine)

    with SessionLocal() as session:
        # Clear old data in correct order
        session.execute(delete(Allergy))
        session.execute(delete(Patient))
        session.commit()

        # Insert patients first
        patients = []
        for patient in data.get("patients", []):
            patient_id = str(patient["patient_id"])
            dob = patient.get("date_of_birth")
            patients.append(
                Patient(
                    patient_id=patient_id,
                    patient_name=patient["patient_name"],
                    date_of_birth=date.fromisoformat(dob) if dob else None,
                    gender=patient.get("gender"),
                    address=patient["address"],
                    contact_number=patient["contact_number"],
                    email=patient["email"],
                )
            )
        session.add_all(patients)
        session.commit()  # Commit before inserting allergies

        # Insert allergies next
        allergies = []
        for patient in data.get("patients", []):
            patient_id = str(patient["patient_id"])
            for allergy in patient.get("allergies", []):
                allergies.append(Allergy(patient_id=patient_id, allergy=allergy))
        if allergies:
            session.add_all(allergies)
            session.commit()

    print(f"Seeded {len(patients)} patients and {len(allergies)} allergies into {DB_URL}")


if __name__ == "__main__":
    seed()