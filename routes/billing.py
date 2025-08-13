from fastapi import APIRouter,HTTPException,Depends,BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import tempfile
import os
from datetime import datetime
from database import engine,get_session
from models import Subscription, Paper, Exclusion, PaperPrice, Frequency, User, BillPaymentStatus
from datetime import date
from calendar import monthrange
from pydantic import BaseModel,RootModel
import re
from config import config
from typing import Dict, List

router = APIRouter()

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

WeekdayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

class BillItem(BaseModel):
    qty: int
    amount: float
    unit_price: float

class BillRequest(BaseModel):
    user_id: int
    year: int
    month: int
    items: Dict[str, BillItem]  # e.g., {"Vijaya Karnataka": {...}}
    total: float
    pending_payments: List[Dict[str, float]]  # can be [] or [{"2025-Jul": 373.0}]
    pending_total: float
    grand_total: float

def get_price(session: Session, paper_id: int, target: date):
    dow = target.weekday()
    rows = session.exec(select(PaperPrice).where(PaperPrice.paper_id==paper_id)).all()
    default = None; day_specific = None
    for r in rows:
        if r.day_of_week is None:
            default = r.price
        elif r.day_of_week == dow:
            day_specific = r.price
    return day_specific if day_specific is not None else (default or 0.0)

def subscription_applies_on(sub: Subscription, target: date):
    if sub.start_date and target < sub.start_date: return False
    if sub.end_date and target > sub.end_date: return False
    dow = target.weekday()
    if sub.frequency == Frequency.DAILY: return True
    if sub.frequency == Frequency.WEEKLY: return sub.weekday == dow
    if sub.frequency == Frequency.MONTHLY: return sub.day_of_month == target.day
    if sub.frequency == Frequency.ALTERNATING:
        if sub.weekday != dow: return False
        if sub.start_date:
            return (target.isocalendar()[1] % 2) == (sub.start_date.isocalendar()[1] % 2)
        return True
    return False

def is_excluded(session: Session, user_id: int, paper_id: int, target: date):
    exs = session.exec(select(Exclusion).where(Exclusion.user_id==user_id)).all()
    for e in exs:
        if e.paper_id is not None and e.paper_id != paper_id: continue
        if e.date_from <= target <= e.date_to:
            return True
    return False

def get_pending_payments(session: Session, user_id: int, year: int, month: int):
    """
    Returns pending payments before the given year/month for a user
    considering subscription start/end dates and payment status.
    """

    results = []
    grand_total = 0.0
    today = date.today()

    # Get subscriptions
    subs = session.exec(
        select(Subscription).where(Subscription.user_id == user_id)
    ).all()
    if not subs:
        return {"pending_payments": [], "grand_total": 0.0,"pending_total": 0.0}

    # Determine the earliest subscription start
    start_date = min(sub.start_date for sub in subs if sub.start_date)
    # End date is either subscription end or today's date
    end_date = max(
        (sub.end_date for sub in subs if sub.end_date), default=today
    )

    # Loop from start_date to the month before given year/month
    cur_year, cur_month = start_date.year, start_date.month
    while (cur_year, cur_month) < (year, month):
        # Check payment status
        payment = session.exec(
            select(BillPaymentStatus).where(
                BillPaymentStatus.user_id == user_id,
                BillPaymentStatus.year == cur_year,
                BillPaymentStatus.month == cur_month - 1 
            )
        ).first()
        print(payment)
        if not payment or payment.status not in ["paid","partial"]:
            days_in_month = monthrange(cur_year, cur_month)[1]
            month_total = 0.0
            # Calculate bill for that month
            for day in range(1, days_in_month + 1):
                cur_date = date(cur_year, cur_month, day)
                for sub in subs:
                    if subscription_applies_on(sub, cur_date) and not is_excluded(session, sub.user_id, sub.paper_id, cur_date):
                        price = get_price(session, sub.paper_id, cur_date)
                        month_total += price

            if month_total > 0:
                month_str = f"{cur_year}-{cur_date.strftime('%b')}"
                results.append({month_str: round(month_total, 2)})
                grand_total += month_total

        elif payment.status == "partial":
            month_str = f"{year}-{MONTH_NAMES[cur_month - 1]}"
            results.append({month_str: round(payment.balance, 2)})
            grand_total += payment.balance
        # Increment month
        if cur_month == 12:
            cur_month = 1
            cur_year += 1
        else:
            cur_month += 1

    return {
        "pending_payments": results,
        "pending_total": round(grand_total, 2)
    }

@router.get("/user/{user_id}")
def monthly_bill(user_id: int, year: int, month: int):
    days = monthrange(year, month)[1]
    items = {}
    total = 0.0
    with Session(engine) as s:
        subs = s.exec(select(Subscription).where(Subscription.user_id==user_id)).all()
        # Pre-fetch all prices for each paper
        paper_prices = {}
        for sub in subs:
            rows = s.exec(select(PaperPrice).where(PaperPrice.paper_id==sub.paper_id)).all()
            paper_prices[sub.paper_id] = rows

        for day in range(1, days+1):
            cur = date(year, month, day)
            dow = cur.weekday()
            for sub in subs:
                if subscription_applies_on(sub, cur) and not is_excluded(s, sub.user_id, sub.paper_id, cur):
                    # Find price and if it's day-specific
                    price = 0.0
                    price_type = "default"
                    for r in paper_prices[sub.paper_id]:
                        if r.day_of_week == dow:
                            price = r.price
                            price_type = WeekdayNames[dow]
                            break
                        elif r.day_of_week is None:
                            price = r.price
                    p = s.get(Paper, sub.paper_id)
                    if price_type != "default":
                        key = f"{p.name} ({price_type})"
                    else:
                        key = p.name
                    if price:
                        items.setdefault(key, {"qty":0, "amount":0.0})
                        if price:
                            items[key]["qty"] += 1
                        items[key]["amount"] += price
                        items[key]["unit_price"] = price
                        total += price
        pending = get_pending_payments(s,user_id,year,month)
    result =  {"user_id": user_id, "year": year, "month": month, "items": items, "total": round(total,2),"pending_payments": pending}
    result.update(pending)
    result["grand_total"] = result["pending_total"] + result["total"]
    return result

@router.get("/bulk")
def bulk_billing(year: int, month: int):
    response = []
    with Session(engine) as s:
        users = s.exec(select(User)).all()
    for user in users:
        user_id = user.id
        days = monthrange(year, month)[1]
        items = {}
        total = 0.0
        with Session(engine) as s:
            subs = s.exec(select(Subscription).where(Subscription.user_id==user_id)).all()
            # Pre-fetch all prices for each paper
            paper_prices = {}
            for sub in subs:
                rows = s.exec(select(PaperPrice).where(PaperPrice.paper_id==sub.paper_id)).all()
                paper_prices[sub.paper_id] = rows

            for day in range(1, days+1):
                cur = date(year, month, day)
                dow = cur.weekday()
                for sub in subs:
                    if subscription_applies_on(sub, cur) and not is_excluded(s, sub.user_id, sub.paper_id, cur):
                        # Find price and if it's day-specific
                        price = 0.0
                        price_type = "default"
                        for r in paper_prices[sub.paper_id]:
                            if r.day_of_week == dow:
                                price = r.price
                                price_type = WeekdayNames[dow]
                                break
                            elif r.day_of_week is None:
                                price = r.price
                        p = s.get(Paper, sub.paper_id)
                        if price_type != "default":
                            key = f"{p.name} ({price_type})"
                        else:
                            key = p.name
                        if price:
                            items.setdefault(key, {"qty":0, "amount":0.0})
                            if price:
                                items[key]["qty"] += 1
                            items[key]["amount"] += price
                            items[key]["unit_price"] = price
                            total += price
        if total > 0:
            result =  {"user_id": user_id,"user_name":user.name, "year": year, "month": month - 1, "status":"unpaid","balance": round(total,2),"amount_paid": 0}
            response.append(result)
    return response


@router.post("/pdf/user")
def generate_bill_for_user(
    data: BillRequest, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_session)
):
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        db.close()
        raise HTTPException(status_code=404, detail="User not found")

    safe_username = re.sub(r"[^a-zA-Z0-9_-]", "_", user.name)
    temp_dir = tempfile.gettempdir()
    file_name = f"bill_{safe_username}_{data.year}_{data.month}.pdf"
    file_path = os.path.join(temp_dir, file_name)

    c = canvas.Canvas(file_path, pagesize=A4)
    c.setTitle(f"Bill for {user.name} - {data.month}/{data.year}")

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 800, f"{config['agency_name']} Newspaper Bill - {user.name}")

    c.setFont("Helvetica", 12)
    c.drawString(100, 780, f"Bill Month: {data.month:02d}/{data.year}")
    c.drawString(100, 765, f"Generated On: {datetime.now().strftime('%Y-%m-%d')}")

    # Table header
    y = 730
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, y, "Paper Name")
    c.drawString(300, y, "Qty")
    c.drawString(400, y, "Unit Price(Rs.)")
    c.drawString(500, y, "Amt(Rs.)")
    y -= 20
    c.line(100, y, 550, y)
    y -= 20

    # Items
    for paper_name, item in data.items.items():
        c.setFont("Helvetica", 11)
        c.drawString(100, y, paper_name)
        c.drawString(300, y, str(item.qty))
        c.drawString(400, y, str(item.unit_price))
        c.drawString(500, y, f"{item.amount:.2f}")
        y -= 20

        if y < 100:
            c.showPage()
            y = 800

    # Total amount
    y -= 10
    c.line(100, y, 550, y)
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, y, "Total Amount:")
    c.drawString(400, y, f"Rs. {data.total:.2f}")

    # Pending payments (if any)
    if data.pending_payments:
        y -= 40
        c.setFont("Helvetica-Bold", 12)
        c.drawString(100, y, "Pending Payments:")
        y -= 20
        c.setFont("Helvetica", 11)
        for pending in data.pending_payments:
            for month_label, amount in pending.items():
                c.drawString(120, y, f"{month_label}: Rs. {amount:.2f}")
                y -= 20
                if y < 100:
                    c.showPage()
                    y = 800

    # Grand total (total + pending payments total)
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, y, "Grand Total:")
    c.drawString(400, y, f"Rs. {data.grand_total:.2f}")

    c.showPage()
    c.save()
    db.close()

    background_tasks.add_task(os.remove, file_path)

    return FileResponse(
        file_path,
        filename=file_name,
        media_type="application/pdf"
    )