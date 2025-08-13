from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from models import BillPaymentStatus,User
from database import get_session
from database import engine
from typing import List
from sqlalchemy import insert

router = APIRouter()

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

@router.post("/", response_model=BillPaymentStatus)
def create_payment_status(
    payment_status: BillPaymentStatus,
    session: Session = Depends(get_session)
):
    print("Creating payment status:", payment_status)
    # Prevent duplicate entries for same month & user
    statement = select(BillPaymentStatus).where(
        BillPaymentStatus.user_id == payment_status.user_id,
        BillPaymentStatus.year == payment_status.year,
        BillPaymentStatus.month == payment_status.month
    )
    existing = session.exec(statement).first()
    if existing:
        raise HTTPException(status_code=400, detail="Payment status already exists for this month")
    session.add(payment_status)
    session.commit()
    session.refresh(payment_status)
    return payment_status

@router.post("/bulk")
def create_bulk_payment_status(payment_statuses: List[BillPaymentStatus],session: Session = Depends(get_session)):
    for payment_status in payment_statuses:
        print("Creating payment status:", payment_status)
        # Prevent duplicate entries for same month & user
        statement = select(BillPaymentStatus).where(
            BillPaymentStatus.user_id == payment_status.user_id,
            BillPaymentStatus.year == payment_status.year,
            BillPaymentStatus.month == payment_status.month
        )
        existing = session.exec(statement).first()
        if existing:
            continue
        session.add(payment_status)
        session.commit()
        session.refresh(payment_status)
    return {"message": "Bulk payment status created successfully", "count": len(payment_statuses)}

@router.get("/")
def get_payment_status():
    with Session(engine) as s:
        results = (
        s.query(
            BillPaymentStatus.id,
            BillPaymentStatus.user_id,
            BillPaymentStatus.year,
            BillPaymentStatus.month,
            BillPaymentStatus.status,
            BillPaymentStatus.amount_paid,
            BillPaymentStatus.balance,
            User.name.label("user_name")
        )
        .join(User,User.id == BillPaymentStatus.user_id)
        .all()
        )

    # Convert SQLAlchemy rows to list of dicts for Pydantic
    rows = [
        {
            "id": r.id,
            "user_id": r.user_id,
            "user_name":r.user_name,
            "year":r.year,
            "status":r.status,
            "month": MONTH_NAMES[r.month] if r.month >=0 and r.month!= None else None,
            "amount_paid": r.amount_paid,
            "balance": r.balance
        }
        for r in results
    ]
    return rows

@router.get("/by-filter")
def get_user_by_filter(user_id: int = None, year: int = None,month :int= None):
    with Session(engine) as s:
        results = (
        s.query(
            BillPaymentStatus.id,
            BillPaymentStatus.user_id,
            BillPaymentStatus.year,
            BillPaymentStatus.month,
            BillPaymentStatus.status,
            BillPaymentStatus.amount_paid,
            BillPaymentStatus.balance,
            User.name.label("user_name")
        )
        .join(User,User.id == BillPaymentStatus.user_id)
        .all()
    )

    # Convert SQLAlchemy rows to list of dicts for Pydantic
    rows = [
        {
            "id": r.id,
            "month": MONTH_NAMES[r.month] if r.month else None,
            "user_id": r.user_id,
            "user_name":r.user_name,
            "year":r.year,
            "status":r.status,
            "amount_paid": r.amount_paid,
            "balance": r.balance
        }
        for r in results
    ]
    if user_id:
        rows = [r for r in rows if r["user_id"] == user_id]
    if year:
        rows = [r for r in rows if r["year"] == year]
    if month:
        month = MONTH_NAMES[month - 1]
        rows = [r for r in rows if r["month"] == month]
    return rows

@router.put("/")
def update_payment(payload: BillPaymentStatus):
    with Session(engine) as s:
        p = s.get(BillPaymentStatus, payload.id)

        if not p:
            return {"error": "not found"}
        for k, v in payload.dict().items():
            if k != "id":
                setattr(p, k, v)
        s.add(p); s.commit(); s.refresh(p)
        p = p.model_dump()
        users = s.get(User, payload.user_id)
        p['user_name'] = users.name
        p['month'] = MONTH_NAMES[p['month']] if p['month'] else None
        return p

@router.delete("/{id}")
def delete_payment(id: int):
    with Session(engine) as s:
        p = s.get(BillPaymentStatus, id)
        if not p:
            raise HTTPException(status_code=404, detail="Payment status not found")
        s.delete(p)
        s.commit()
        return {"message": "Payment status deleted successfully"}