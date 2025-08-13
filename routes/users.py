from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from database import engine
from models import User
from schemas import UserCreate,UserPut

router = APIRouter()

@router.post("/", response_model=UserCreate)
def create_user(payload: UserCreate):
    u = User(name=payload.name, mobile=payload.mobile, flat_id=payload.flat_id, apt_name=payload.apt_name)
    with Session(engine) as s:
        s.add(u); s.commit(); s.refresh(u)
    return payload

@router.get("/")
def list_users():
    with Session(engine) as s:
        return s.exec(select(User)).all()

@router.get("/by-filter")
def get_user_by_filter(mobile: str = None, flat_id: str = None):
    with Session(engine) as s:
        stmt = select(User)
        rows = s.exec(stmt).all()
        if mobile:
            rows = [r for r in rows if r.mobile == mobile]
        if flat_id:
            rows = [r for r in rows if r.flat_id == flat_id]
        return rows

@router.put("/")
def update_exclusion(payload: UserPut):
    with Session(engine) as s:
        ex = s.get(User, payload.id)
        if not ex:
            return {"error": "not found"}
        for k, v in payload.model_dump().items():
            if k != "id":
                setattr(ex, k, v)
        s.add(ex)
        s.commit()
        s.refresh(ex)
        return ex

@router.delete("/{user_id}")
def delete_exclusion(user_id: int):
    with Session(engine) as s:
        ex = s.get(User, user_id)
        if ex:
            s.delete(ex)
            s.commit()
        return {"ok": True}