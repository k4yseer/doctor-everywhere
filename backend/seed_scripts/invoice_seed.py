import json
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import Column, DateTime, Numeric, String, create_engine, delete
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]
SEED_PATH = BASE_DIR / "seed_scripts" / "common_seed.json"
DB_URL = os.environ.get("dbURL", "mysql+pymysql://root:root@localhost:3306/invoice_db")

Base = declarative_base()
engine = create_engine(DB_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Invoice(Base):
    __tablename__ = "invoices"

    invoice_id = Column(String(64), primary_key=True)
    appointment_id = Column(String(64), nullable=False)
    patient_id = Column(String(64), nullable=False)
    consultation_fee = Column(Numeric(10, 2), nullable=False, default=0.0)
    medicine_fee = Column(Numeric(10, 2), nullable=False, default=0.0)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(8), nullable=False)
    payment_status = Column(String(32), nullable=False)
    stripe_charge_id = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False)


def load_seed_data():
    with open(SEED_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def seed():
    data = load_seed_data()

    Base.metadata.create_all(engine)

    with SessionLocal() as session:
        session.execute(delete(Invoice))
        session.commit()

        invoices = []
        for item in data["invoices"]:
            invoices.append(
                Invoice(
                    invoice_id=item["invoice_id"],
                    appointment_id=str(item["appointment_id"]),
                    patient_id=str(item["patient_id"]),
                    consultation_fee=item["consultation_fee"],
                    medicine_fee=item["medicine_fee"],
                    amount=item["amount"],
                    currency=item["currency"],
                    payment_status=item["payment_status"],
                    stripe_charge_id=item.get("stripe_charge_id"),
                    created_at=datetime.fromisoformat(item["created_at"]),
                )
            )

        session.add_all(invoices)
        session.commit()

    print(f"Seeded {len(invoices)} invoices into {DB_URL}")


if __name__ == "__main__":
    seed()
