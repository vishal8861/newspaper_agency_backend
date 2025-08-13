from fastapi import APIRouter,Depends
from sqlmodel import Session, select
from database import engine,get_session
from models import Subscription,Paper,User
from schemas import SubscriptionCreate,SubscriptionPut

DAYS = {0:"Monday", 1:"Tuesday", 2:"Wednesday", 3:"Thursday", 4:"Friday", 5:"Saturday", 6:"Sunday",None:None}

router = APIRouter()

@router.post("/")
def create_subscription(payload: SubscriptionCreate):
    sub = Subscription(
        user_id=payload.user_id,
        paper_id=payload.paper_id,
        frequency=payload.frequency,
        weekday=payload.weekday,
        day_of_month=payload.day_of_month,
        start_date=payload.start_date,
        end_date=payload.end_date
    )
    with Session(engine) as s:
        s.add(sub); s.commit(); s.refresh(sub)
    return sub

@router.get("/")
def list_subscriptions(db: Session = Depends(get_session)):
    results = (
        db.query(
            Subscription.id,
            Subscription.paper_id,
            Subscription.day_of_month,
            Subscription.user_id,
            Subscription.frequency,
            Subscription.weekday,
            Subscription.start_date,
            Subscription.end_date,
            Paper.name.label("paper_name"),
            User.name.label("user_name")
        )
        .join(Paper, Paper.id == Subscription.paper_id)
        .join(User,User.id == Subscription.user_id)
        .all()
    )

    # Convert SQLAlchemy rows to list of dicts for Pydantic
    return [
        {
            "id": r.id,
            "day_of_month": r.day_of_month,
            "user_id": r.user_id,
            "user_name":r.user_name,
            "paper_id": r.paper_id,
            "paper_name": r.paper_name,
            "frequency":r.frequency,
            "weekday":DAYS[r.weekday],
            "start_date":r.start_date,
            "end_date":r.end_date
        }
        for r in results
    ]

@router.get("/filter")
def filter_subscriptions(user_id:int=None,paper_id:int=None):
    with Session(engine) as db:
        results = (
            db.query(
                Subscription.id,
                Subscription.paper_id,
                Subscription.day_of_month,
                Subscription.user_id,
                Subscription.frequency,
                Subscription.weekday,
                Subscription.start_date,
                Subscription.end_date,
                Paper.name.label("paper_name"),
                User.name.label("user_name")
            )
            .join(Paper, Paper.id == Subscription.paper_id)
            .join(User,User.id == Subscription.user_id)
            .all()
        )
    rows = [
        {
            "id": r.id,
            "day_of_month": r.day_of_month,
            "user_id": r.user_id,
            "user_name":r.user_name,
            "paper_id": r.paper_id,
            "paper_name": r.paper_name,
            "frequency":r.frequency,
            "weekday":DAYS[r.weekday],
            "start_date":r.start_date,
            "end_date":r.end_date
        }
        for r in results if (not user_id or r.user_id == user_id) and (not paper_id or r.paper_id == paper_id)
    ]

    if user_id:
        rows = [r for r in rows if r['user_id'] == user_id]
    if paper_id:
        rows = [r for r in rows if r['paper_id'] == paper_id]
    return rows

@router.get("/{sub_id}")
def get_subscription(sub_id: int):
    with Session(engine) as s:
        return s.get(Subscription, sub_id)

@router.put("/")
def update_subscription(payload: SubscriptionPut):
    with Session(engine) as s:
        sub = s.get(Subscription, payload.id)
        if not sub:
            return {"error": "not found"}
        for k, v in payload.dict().items():
            if k != "id":
                setattr(sub, k, v)
        s.add(sub); s.commit(); s.refresh(sub)
        return sub

@router.delete("/{sub_id}")
def delete_subscription(sub_id: int):
    with Session(engine) as s:
        sub = s.get(Subscription, sub_id)
        if sub:
            s.delete(sub); s.commit()
        return {"ok": True}