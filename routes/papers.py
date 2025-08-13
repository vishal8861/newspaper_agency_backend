from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from database import engine,get_session
from models import Paper, PaperPrice
from schemas import PaperCreate, PriceCreate

router = APIRouter()

@router.post("/")
def create_paper(payload: PaperCreate):
    p = Paper(name=payload.name)
    with Session(engine) as s:
        s.add(p); s.commit(); s.refresh(p)
    return p

@router.get("/")
def list_papers():
    with Session(engine) as s:
        return s.exec(select(Paper)).all()

@router.put("/")
def update_exclusion(payload: Paper):
    with Session(engine) as s:
        ex = s.get(Paper, payload.id)
        if not ex:
            return {"error": "not found"}
        for k, v in payload.model_dump().items():
            if k != "id":
                setattr(ex, k, v)
        s.add(ex)
        s.commit()
        s.refresh(ex)
        return ex

@router.post("/{paper_id}/price")
def set_price(paper_id: int, payload: PriceCreate):
    pp = PaperPrice(paper_id=paper_id, day_of_week=payload.day_of_week, price=payload.price)
    with Session(engine) as s:
        s.add(pp); s.commit(); s.refresh(pp)
    return pp

@router.get("/paperprice")
def get_paper_prices(db: Session = Depends(get_session)):
    results = (
        db.query(
            PaperPrice.id,
            PaperPrice.paper_id,
            PaperPrice.day_of_week,
            PaperPrice.price,
            Paper.name.label("paper_name")
        )
        .join(Paper, Paper.id == PaperPrice.paper_id)
        .all()
    )

    # Convert SQLAlchemy rows to list of dicts for Pydantic
    return [
        {
            "id": r.id,
            "paper_id": r.paper_id,
            "day_of_week": r.day_of_week,
            "price": r.price,
            "paper_name": r.paper_name
        }
        for r in results
    ]

@router.put("/paperprice")
def update_exclusion(payload: PaperPrice):
    with Session(engine) as s:
        ex = s.get(PaperPrice, payload.id)
        if not ex:
            return {"error": "not found"}
        for k, v in payload.model_dump().items():
            if k != "id":
                setattr(ex, k, v)
        s.add(ex)
        s.commit()
        s.refresh(ex)
        papers = s.get(Paper, payload.paper_id)
        ex = ex.model_dump()
        ex['paper_name'] = papers.name
        return ex

@router.delete("/paperprice/{price_id}")
def delete_exclusion(price_id: int):
    with Session(engine) as s:
        ex = s.get(PaperPrice, price_id)
        if ex:
            s.delete(ex)
            s.commit()
        return {"ok": True}
