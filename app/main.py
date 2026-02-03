from fastapi import FastAPI, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from .db import Base, engine, get_db
from .models import User, Patient, Claim, AuditLog
from .auth import (
    hash_password, verify_password,
    login_user, logout_user,
    get_current_user, require_roles
)
from .services import write_audit, dashboard_metrics, approve_claim, reject_claim

app = FastAPI()


app.add_middleware(SessionMiddleware, secret_key="dev-secret-change-me")

templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def startup():
   
    Base.metadata.create_all(bind=engine)

    from sqlalchemy.orm import Session as OrmSession
    db = OrmSession(bind=engine)

    existing = db.execute(select(User).limit(1)).scalar_one_or_none()
    if not existing:
        admin = User(email="admin@demo.com", password_hash=hash_password("Admin@123"), role="admin")
        staff = User(email="staff@demo.com", password_hash=hash_password("Staff@123"), role="staff")
        patient = User(email="patient@demo.com", password_hash=hash_password("Patient@123"), role="patient")
        db.add_all([admin, staff, patient])
        db.commit()

    db.close()


@app.get("/")
def home():
    return RedirectResponse("/dashboard", status_code=302)



@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
def login(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
):
    user = db.execute(select(User).where(User.email == email.strip().lower())).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

    login_user(request, user)
    write_audit(db, actor_id=user.id, action="LOGIN", entity_type="users", entity_id=user.id, metadata={"email": user.email})
    return RedirectResponse("/dashboard", status_code=302)


@app.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    try:
        user = get_current_user(request, db)
        write_audit(db, actor_id=user.id, action="LOGOUT", entity_type="users", entity_id=user.id, metadata={"email": user.email})
    except Exception:
        pass

    logout_user(request)
    return RedirectResponse("/login", status_code=302)

@app.get("/signup")
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request, "error": None})



@app.post("/signup")
def signup(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    dob: str = Form(...),
    phone: str = Form(""),
):
    email_norm = email.strip().lower()
    if not email_norm:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Email required"})
    if len(password) < 6:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Password must be at least 6 chars"})
    if not full_name.strip() or not dob.strip():
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Full name and DOB required"})

    existing = db.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()
    if existing:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Email already registered"})

 
    admin_user = db.execute(
        select(User).where(User.role == "admin").order_by(User.id)
    ).scalar_one_or_none()
    admin_id = admin_user.id if admin_user else 1

  
    patient = Patient(
        full_name=full_name.strip(),
        dob=dob.strip(),
        phone=phone.strip() or None,
        created_by=admin_id,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    # create user linked to patient
    user = User(
        email=email_norm,
        password_hash=hash_password(password),
        role="patient",
        patient_id=patient.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    write_audit(
        db,
        actor_id=user.id,
        action="SIGNUP",
        entity_type="users",
        entity_id=user.id,
        metadata={"email": user.email, "patient_id": patient.id},
    )

    login_user(request, user)
    return RedirectResponse("/dashboard", status_code=302)





@app.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    try:
        user = get_current_user(request, db)
    except Exception:
        return RedirectResponse("/login", status_code=302)

    metrics = dashboard_metrics(db, user.role, user.id)

    can_manage_patients = user.role in {"admin", "staff"}
    can_approve_claims = user.role in {"admin", "staff"}
    can_view_audit = user.role == "admin"

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "metrics": metrics,
            "can_manage_patients": can_manage_patients,
            "can_approve_claims": can_approve_claims,
            "can_view_audit": can_view_audit,
        },
    )



@app.get("/patients")
def patients_list(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_roles(user, {"admin", "staff"})


    patients = db.execute(select(Patient).order_by(desc(Patient.id))).scalars().all()
    return templates.TemplateResponse("patients_list.html", {"request": request, "user": user, "patients": patients})


@app.get("/patients/new")
def patient_new_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_roles(user, {"admin", "staff"})

    return templates.TemplateResponse("patient_form.html", {"request": request, "user": user, "error": None})


@app.post("/patients/new")
def patient_create(
    request: Request,
    db: Session = Depends(get_db),
    full_name: str = Form(...),
    dob: str = Form(...),
    phone: str = Form(""),
):
    user = get_current_user(request, db)
    require_roles(user, {"admin", "staff"})


    if not full_name.strip():
        return templates.TemplateResponse("patient_form.html", {"request": request, "user": user, "error": "Name required"})
    if not dob.strip():
        return templates.TemplateResponse("patient_form.html", {"request": request, "user": user, "error": "DOB required"})

    patient = Patient(full_name=full_name.strip(), dob=dob.strip(), phone=phone.strip() or None, created_by=user.id)
    db.add(patient)
    db.commit()
    db.refresh(patient)

    write_audit(db, actor_id=user.id, action="CREATE_PATIENT", entity_type="patients", entity_id=patient.id, metadata={"name": patient.full_name})
    return RedirectResponse("/patients", status_code=302)



@app.get("/claims")
def claims_list(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    
    if user.role == "patient":
        claims = db.execute(select(Claim).where(Claim.submitted_by == user.id).order_by(desc(Claim.id))).scalars().all()
    else:
        claims = db.execute(select(Claim).order_by(desc(Claim.id))).scalars().all()

    return templates.TemplateResponse("claims_list.html", {"request": request, "user": user, "claims": claims})


@app.get("/claims/new")
def claim_new_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_roles(user, {"admin", "staff"})

    patients = []
    if user.role in {"admin", "staff"}:
        patients = db.execute(select(Patient).order_by(desc(Patient.id))).scalars().all()

    return templates.TemplateResponse(
        "claim_form.html",
        {"request": request, "user": user, "patients": patients, "error": None},
    )


@app.post("/claims/new")
def claim_create(
    request: Request,
    db: Session = Depends(get_db),
    patient_id: int = Form(...),
    amount: float = Form(...),
    payer: str = Form(...),
    service_date: str = Form(...),
    description: str = Form(""),
):
    user = get_current_user(request, db)
    require_roles(user, {"admin", "staff"})
    
    if user.role == "patient":
        if not user.patient_id:
            return templates.TemplateResponse("claim_form.html", {"request": request, "user": user, "patients": [], "error": "Patient profile not linked"})
        patient_id = user.patient_id


    if amount <= 0:
        patients = db.execute(select(Patient).order_by(desc(Patient.id))).scalars().all()
        return templates.TemplateResponse("claim_form.html", {"request": request, "user": user, "patients": patients, "error": "Amount must be > 0"})

    claim = Claim(
        patient_id=patient_id,
        submitted_by=user.id,
        amount=amount,
        payer=payer.strip(),
        service_date=service_date.strip(),
        description=description.strip() or None,
        status="PENDING",
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    write_audit(db, actor_id=user.id, action="SUBMIT_CLAIM", entity_type="claims", entity_id=claim.id, metadata={"amount": amount, "payer": payer})
    return RedirectResponse("/claims", status_code=302)


@app.get("/claims/{claim_id}")
def claim_detail(request: Request, claim_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)

    claim = db.execute(select(Claim).where(Claim.id == claim_id)).scalar_one_or_none()
    if not claim:
        return RedirectResponse("/claims", status_code=302)

    
    if user.role == "patient" and claim.submitted_by != user.id:
        return RedirectResponse("/claims", status_code=302)

    can_decide = user.role in {"admin", "staff"}
    return templates.TemplateResponse("claim_detail.html", {"request": request, "user": user, "claim": claim, "can_decide": can_decide, "error": None})


@app.post("/claims/{claim_id}/approve")
def claim_approve(request: Request, claim_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_roles(user, {"admin", "staff"})


    claim = db.execute(select(Claim).where(Claim.id == claim_id)).scalar_one_or_none()
    if not claim:
        return RedirectResponse("/claims", status_code=302)

    try:
        approve_claim(db, claim, actor_id=user.id)
        write_audit(db, actor_id=user.id, action="APPROVE_CLAIM", entity_type="claims", entity_id=claim.id, metadata={"amount": claim.amount})
    except ValueError as e:
        return templates.TemplateResponse("claim_detail.html", {"request": request, "user": user, "claim": claim, "can_decide": True, "error": str(e)})

    return RedirectResponse(f"/claims/{claim_id}", status_code=302)


@app.post("/claims/{claim_id}/reject")
def claim_reject(
    request: Request,
    claim_id: int,
    db: Session = Depends(get_db),
    reason: str = Form(...),
):
    user = get_current_user(request, db)
    require_roles(user, {"admin", "staff"})


    claim = db.execute(select(Claim).where(Claim.id == claim_id)).scalar_one_or_none()
    if not claim:
        return RedirectResponse("/claims", status_code=302)

    try:
        reject_claim(db, claim, actor_id=user.id, reason=reason)
        write_audit(db, actor_id=user.id, action="REJECT_CLAIM", entity_type="claims", entity_id=claim.id, metadata={"reason": reason})
    except ValueError as e:
        return templates.TemplateResponse("claim_detail.html", {"request": request, "user": user, "claim": claim, "can_decide": True, "error": str(e)})

    return RedirectResponse(f"/claims/{claim_id}", status_code=302)


@app.get("/audit")
def audit_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_roles(user, {"admin"})

    logs = db.execute(select(AuditLog).order_by(desc(AuditLog.id)).limit(200)).scalars().all()
    return templates.TemplateResponse("audit.html", {"request": request, "user": user, "logs": logs})

@app.get("/patients/{patient_id}/edit")
def patient_edit_page(request: Request, patient_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_roles(user, {"admin", "staff"})

    patient = db.execute(select(Patient).where(Patient.id == patient_id)).scalar_one_or_none()
    if not patient:
        return RedirectResponse("/patients", status_code=302)

    return templates.TemplateResponse("patient_edit.html", {"request": request, "user": user, "patient": patient, "error": None})


@app.post("/patients/{patient_id}/edit")
def patient_update(
    request: Request,
    patient_id: int,
    db: Session = Depends(get_db),
    full_name: str = Form(...),
    dob: str = Form(...),
    phone: str = Form(""),
):
    user = get_current_user(request, db)
    require_roles(user, {"admin", "staff"})

    patient = db.execute(select(Patient).where(Patient.id == patient_id)).scalar_one_or_none()
    if not patient:
        return RedirectResponse("/patients", status_code=302)
 
    if not full_name.strip() or not dob.strip():
        return templates.TemplateResponse("patient_edit.html", {"request": request, "user": user, "patient": patient, "error": "Name and DOB required"})

    patient.full_name = full_name.strip()
    patient.dob = dob.strip()
    patient.phone = phone.strip() or None
    db.commit()

    write_audit(db, actor_id=user.id, action="UPDATE_PATIENT", entity_type="patients", entity_id=patient.id, metadata={"name": patient.full_name})
    return RedirectResponse("/patients", status_code=302)


@app.post("/patients/{patient_id}/delete")
def patient_delete(request: Request, patient_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    require_roles(user, {"admin"})  

    patient = db.execute(select(Patient).where(Patient.id == patient_id)).scalar_one_or_none()
    if not patient:
        return RedirectResponse("/patients", status_code=302)

   
    existing_claim = db.execute(select(Claim).where(Claim.patient_id == patient_id).limit(1)).scalar_one_or_none()
    if existing_claim:
        return RedirectResponse("/patients", status_code=302)

    db.delete(patient)
    db.commit()

    write_audit(db, actor_id=user.id, action="DELETE_PATIENT", entity_type="patients", entity_id=patient_id, metadata=None)
    return RedirectResponse("/patients", status_code=302)
