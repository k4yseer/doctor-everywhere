from app.database import SessionLocal
from app.models import Patient, Allergies
from sqlalchemy import delete

def seed_database():
    """Insert dummy records into the database."""
    session = SessionLocal()

    session.execute(delete(Allergies))
    session.execute(delete(Patient))

    patients = [
        Patient(
            patient_id="10000001",
            patient_name="John Doe",
            address="123 Main St",
            contact_number="93456789",
            email="john@example.com",
        ),
        Patient(
            patient_id="10000002",
            patient_name="Jane Smith",
            address="456 Oak Ave",
            contact_number="98765432",
            email="jane@example.com",
        ),
    ]
    session.add_all(patients)
    session.commit()

    allergies = [
        Allergies(patient_id="10000001", allergy="Penicillin"),
        Allergies(patient_id="10000001", allergy="Aspirin"),
        Allergies(patient_id="10000002", allergy="Ibuprofen"),
    ]
    session.add_all(allergies)
    session.commit()
    session.close()
    print("Database seeded!")


# expose a Flask CLI command so that the module can be imported without
# forcibly executing anything when the app starts.

def register_cli(app):
    @app.cli.command("seed")
    def _seed():
        """Seed the database with dummy data."""
        seed_database()
