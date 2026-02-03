from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from .db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)

    
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

   
    patient = relationship("Patient", foreign_keys=[patient_id])

  
    created_patients = relationship(
        "Patient",
        back_populates="created_by_user",
        foreign_keys="Patient.created_by",
    )

    submitted_claims = relationship(
        "Claim",
        back_populates="submitted_by_user",
        foreign_keys="Claim.submitted_by",
    )

    decided_claims = relationship(
        "Claim",
        back_populates="decision_by_user",
        foreign_keys="Claim.decision_by",
    )


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True)
    full_name = Column(String(255), nullable=False)
    dob = Column(String(20), nullable=False)
    phone = Column(String(50), nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    created_by_user = relationship(
        "User",
        back_populates="created_patients",
        foreign_keys=[created_by],
    )

    claims = relationship("Claim", back_populates="patient")


class Claim(Base):
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    submitted_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    amount = Column(Float, nullable=False)
    payer = Column(String(255), nullable=False)
    service_date = Column(String(20), nullable=False)
    description = Column(Text, nullable=True)

    status = Column(String(20), default="PENDING", nullable=False)

    decision_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decision_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    patient = relationship("Patient", back_populates="claims")

    submitted_by_user = relationship(
        "User",
        foreign_keys=[submitted_by],
        back_populates="submitted_claims",
    )

    decision_by_user = relationship(
        "User",
        foreign_keys=[decision_by],
        back_populates="decided_claims",
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)

    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

