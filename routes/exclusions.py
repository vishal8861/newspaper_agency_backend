from fastapi import APIRouter,Depends
from sqlmodel import Session, select
from database import engine,get_session
from models import Exclusion,Paper,User
from schemas import ExclusionCreate,ExclusionPut

router = APIRouter()

@router.post("/")
def create_exclusion(payload: ExclusionCreate):
    ex = Exclusion(
        user_id=payload.user_id,
        paper_id=payload.paper_id,
        date_from=payload.date_from,
        date_to=payload.date_to
    )
    with Session(engine) as s:
        s.add(ex); s.commit(); s.refresh(ex)
    return ex

@router.get("/")
def list_subscriptions(db: Session = Depends(get_session)):
    results = (
        db.query(
            Exclusion.id,
            Exclusion.paper_id,
            Exclusion.user_id,
            Exclusion.date_from,
            Exclusion.date_to,
            Paper.name.label("paper_name"),
            User.name.label("user_name")
        )
        .join(Paper, Paper.id == Exclusion.paper_id)
        .join(User,User.id == Exclusion.user_id)
        .all()
    )

    # Convert SQLAlchemy rows to list of dicts for Pydantic
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "user_name":r.user_name,
            "paper_id": r.paper_id,
            "paper_name": r.paper_name,
            "date_from":r.date_from,
            "date_to":r.date_to
        }
        for r in results
    ]

@router.put("/")
def update_exclusion(payload: ExclusionPut):
    with Session(engine) as s:
        ex = s.get(Exclusion, payload.id)
        if not ex:
            return {"error": "not found"}
        for k, v in payload.model_dump().items():
            if k != "id":
                setattr(ex, k, v)
        s.add(ex)
        s.commit()
        s.refresh(ex)
        return ex

@router.delete("/{exclusion_id}")
def delete_exclusion(exclusion_id: int):
    with Session(engine) as s:
        ex = s.get(Exclusion, exclusion_id)
        if ex:
            s.delete(ex)
            s.commit()
        return {"ok": True}
