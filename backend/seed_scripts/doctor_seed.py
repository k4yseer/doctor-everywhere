import json
import os
from pathlib import Path

from sqlalchemy import Column, Enum, Integer, String, create_engine, delete
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]
SEED_PATH = BASE_DIR / "seed_scripts" / "common_seed.json"
DB_URL = os.environ.get("dbURL", "mysql+pymysql://root:root@localhost:3306/doctor_db")

Base = declarative_base()
engine = create_engine(DB_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    specialty = Column(String(128), nullable=False)
    status = Column(Enum("AVAILABLE", "UNAVAILABLE"), nullable=False, default="AVAILABLE")


def load_seed_data():
    with open(SEED_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def seed():
    data = load_seed_data()

    Base.metadata.create_all(engine)

    with SessionLocal() as session:
        session.execute(delete(Doctor))
        session.commit()

        doctors = [
            Doctor(
                id=doc["id"],
                name=doc["name"],
                specialty=doc["specialty"],
                status=doc["status"],
            )
            for doc in data["doctors"]
        ]

        session.add_all(doctors)
        session.commit()

    print(f"Seeded {len(doctors)} doctors into {DB_URL}")


if __name__ == "__main__":
    seed()
