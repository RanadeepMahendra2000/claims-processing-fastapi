import json
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from .models import AuditLog, Claim, Patient


def write_audit(db: Session, actor_id: int, action: str, entity_type: str, entity_id: int, metadata: dict | None = None):

    log = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    db.add(log)
    db.commit()


def dashboard_metrics(db: Session, user_role: str, user_id: int):
    """
    Compute dashboard cards.
    If Patient -> scope to only claims submitted_by user_id.
    """
    claim_filter = []
    if user_role == "patient":
        claim_filter = [Claim.submitted_by == user_id]

    total_claims = db.execute(select(func.count(Claim.id)).where(*claim_filter)).scalar() or 0
    pending_claims = db.execute(select(func.count(Claim.id)).where(*claim_filter, Claim.status == "PENDING")).scalar() or 0
    approved_claims = db.execute(select(func.count(Claim.id)).where(*claim_filter, Claim.status == "APPROVED")).scalar() or 0
    rejected_claims = db.execute(select(func.count(Claim.id)).where(*claim_filter, Claim.status == "REJECTED")).scalar() or 0


    total_amount = db.execute(select(func.coalesce(func.sum(Claim.amount), 0.0)).where(*claim_filter)).scalar() or 0.0
    approved_amount = db.execute(select(func.coalesce(func.sum(Claim.amount), 0.0)).where(*claim_filter, Claim.status == "APPROVED")).scalar() or 0.0

   
    total_patients = 0
    if user_role in {"admin", "staff"}:
        total_patients = db.execute(select(func.count(Patient.id))).scalar() or 0

    
    approval_rate = 0
    if total_claims > 0:
        approval_rate = round((approved_claims / total_claims) * 100)

    return {
        "total_claims": total_claims,
        "pending_claims": pending_claims,
        "approved_claims": approved_claims,
        "rejected_claims": rejected_claims,
        "total_patients": total_patients,
        "total_amount": round(float(total_amount), 2),
        "approved_amount": round(float(approved_amount), 2),
        "approval_rate": approval_rate,
    }


def approve_claim(db: Session, claim: Claim, actor_id: int):
   
    if claim.status != "PENDING":
        raise ValueError("Only PENDING claims can be approved")

    claim.status = "APPROVED"
    claim.decision_by = actor_id
    claim.decision_reason = None
    claim.updated_at = datetime.utcnow()
    db.commit()


def reject_claim(db: Session, claim: Claim, actor_id: int, reason: str):
  
    if claim.status != "PENDING":
        raise ValueError("Only PENDING claims can be rejected")
    if not reason.strip():
        raise ValueError("Rejection reason is required")

    claim.status = "REJECTED"
    claim.decision_by = actor_id
    claim.decision_reason = reason.strip()
    claim.updated_at = datetime.utcnow()
    db.commit()
