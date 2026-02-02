# Claims Processing System (FastAPI)

A simple end-to-end **Python full-stack** demo app that simulates hospital claims workflows:
- Patient creation + listing
- Claims submission + listing + detail view
- Approve/Reject workflow with validation rules
- Dashboard metrics (counts + amounts + approval rate)
- Audit logging for key actions
- Role-based access (Admin/Staff/Patient)

> Built with a simple server-rendered UI (Jinja2 templates) to keep the frontend lightweight while maintaining correct backend functionality.

---

## Tech Stack
- **Backend:** FastAPI (Python)
- **Frontend:** Jinja2 templates (HTML forms, server-rendered)
- **DB:** SQLite + SQLAlchemy ORM
- **Auth:** Session cookie (Starlette SessionMiddleware) + RBAC
- **Audit:** `audit_logs` table

---

## Demo Accounts
| Role    | Email             | Password      |
|---------|-------------------|---------------|
| Admin   | admin@demo.com    | Admin@123     |
| Staff   | staff@demo.com    | Staff@123     |
| Patient | patient@demo.com  | Patient@123   |

Demo users are auto-created on startup if the database is empty.

---

## Features
### Authentication + RBAC
- Login/logout
- Roles:
  - **Admin**: full access + audit log page
  - **Staff**: manage patients + submit/approve/reject claims
  - **Patient**: view only their own claims (prevents URL ID-guessing)

### Patient Management (Admin/Staff)
- Create patient
- List patients

### Claims Workflow
- Create claim (PENDING)
- View claims list + claim detail
- Approve claim (only if PENDING)
- Reject claim (only if PENDING, reason required)

### Dashboard Metrics
- Total / pending / approved / rejected claims
- Total amount + approved amount
- Approval rate
- Total patients (admin/staff)

### Audit Trail (Admin)
Logs actions like:
- LOGIN, LOGOUT
- CREATE_PATIENT
- SUBMIT_CLAIM
- APPROVE_CLAIM, REJECT_CLAIM

---

## Local Setup

### 1) Create venv + install
```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
