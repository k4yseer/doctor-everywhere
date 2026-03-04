from sqlalchemy import Column, ForeignKey, String
from app.database import Base

class Patient(Base):
    __tablename__ = 'patients'

    patient_id = Column(String(8), primary_key=True)
    patient_name = Column(String(64), nullable=False)
    address = Column(String(64), nullable=False)
    contact_number = Column(String(8), nullable=False)
    email = Column(String(64), nullable=False)

    def json(self):
        return {
            "patient_id": self.patient_id,
            "patient_name": self.patient_name,
            "address": self.address,
            "contact_number": self.contact_number,
            "email": self.email
        }


class Allergies(Base):
    __tablename__ = 'allergies'

    patient_id = Column(ForeignKey(
        'patients.patient_id', ondelete='CASCADE', onupdate='CASCADE'), primary_key=True)
    allergy = Column(String(64), primary_key=True)

