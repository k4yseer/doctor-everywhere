import json
import os
from pathlib import Path

from sqlalchemy import Column, String, Text, create_engine, delete
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]
SEED_PATH = BASE_DIR / "seed_scripts" / "common_seed.json"
DB_URL = os.environ.get("dbURL", "mysql+pymysql://root:root@localhost:3306/delivery_db")

Base = declarative_base()
engine = create_engine(DB_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Delivery(Base):
    __tablename__ = "delivery"

    delivery_id = Column(String(36), primary_key=True)
    appointment_id = Column(String(36), nullable=False)
    patient_address = Column(Text, nullable=False)
    tracking_number = Column(String(100), nullable=True)
    delivery_status = Column(String(20), nullable=False, default="PENDING")


def load_seed_data():
    with open(SEED_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def seed():
    data = load_seed_data()

    Base.metadata.create_all(engine)

    with SessionLocal() as session:
        session.execute(delete(Delivery))
        session.commit()

        deliveries = []
        for item in data["deliveries"]:
            deliveries.append(
                Delivery(
                    delivery_id=item["delivery_id"],
                    appointment_id=str(item["appointment_id"]),
                    patient_address=item["patient_address"],
                    tracking_number=item.get("tracking_number"),
                    delivery_status=item["delivery_status"],
                )
            )

        session.add_all(deliveries)
        session.commit()

    print(f"Seeded {len(deliveries)} deliveries into {DB_URL}")


if __name__ == "__main__":
    seed()
