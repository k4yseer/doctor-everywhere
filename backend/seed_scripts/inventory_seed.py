import json
import os
from pathlib import Path

from sqlalchemy import Column, Integer, Numeric, String, create_engine, delete
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parents[1]
SEED_PATH = BASE_DIR / "seed_scripts" / "common_seed.json"
DB_URL = os.environ.get("dbURL", "mysql+pymysql://root:root@localhost:3306/inventory_db")

Base = declarative_base()
engine = create_engine(DB_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Medicine(Base):
    __tablename__ = "medicine"

    medicine_code = Column(String(50), primary_key=True)
    medicine_name = Column(String(255), nullable=False)
    stock_available = Column(Integer, nullable=False, default=0)
    unit_price = Column(Numeric(10, 2), nullable=False, default=0.0)


class Reservation(Base):
    __tablename__ = "reservations"

    reservation_id = Column(Integer, primary_key=True, autoincrement=True)
    medicine_code = Column(String(50), nullable=False)
    appointment_id = Column(Integer, nullable=False)
    amount = Column(Integer, nullable=False)


def load_seed_data():
    with open(SEED_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def seed():
    data = load_seed_data()

    Base.metadata.create_all(engine)

    with SessionLocal() as session:
        session.execute(delete(Reservation))
        session.execute(delete(Medicine))
        session.commit()

        medicines = [
            Medicine(
                medicine_code=med["medicine_code"],
                medicine_name=med["medicine_name"],
                stock_available=med["stock_available"],
                unit_price=med["unit_price"],
            )
            for med in data.get("medicines", [])
        ]

        reservations = [
            Reservation(
                reservation_id=res["reservation_id"],
                medicine_code=res["medicine_code"],
                appointment_id=res["appointment_id"],
                amount=res["amount"],
            )
            for res in data.get("reservations", [])
        ]

        session.add_all(medicines)
        session.add_all(reservations)
        session.commit()

    print(f"Seeded {len(medicines)} medicines and {len(reservations)} reservations into {DB_URL}")


if __name__ == "__main__":
    seed()
