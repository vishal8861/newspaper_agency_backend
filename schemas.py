from pydantic import BaseModel
from typing import Optional
from datetime import date
from enum import Enum

class Frequency(str, Enum):
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    ALTERNATING = 'alternating'

class UserCreate(BaseModel):
    name: str
    mobile: str
    flat_id: str
    apt_name: str

class UserPut(BaseModel):
    id: int
    name: str
    mobile: str
    flat_id: str
    apt_name: str

class PaperCreate(BaseModel):
    name: str

class PriceCreate(BaseModel):
    day_of_week: Optional[int] = None
    price: float

class SubscriptionCreate(BaseModel):
    user_id: int
    paper_id: int
    frequency: Frequency
    weekday: Optional[int] = None
    day_of_month: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class SubscriptionPut(BaseModel):
    id: int
    user_id: int
    paper_id: int
    frequency: Frequency
    weekday: Optional[int] = None
    day_of_month: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class ExclusionCreate(BaseModel):
    user_id: int
    paper_id: Optional[int] = None
    date_from: date
    date_to: date

class ExclusionPut(BaseModel):
    id: int
    user_id: int
    paper_id: Optional[int] = None
    date_from: date
    date_to: date

class PaperPriceBase(BaseModel):
    id: int
    paper_id: int
    day_pattern: str
    price: float

class PaperPriceWithName(PaperPriceBase):
    id: int
    paper_name: str  # ✅ Only for response
    class Config:
        from_attributes = True

class SubscriptionBase(BaseModel):
    id: int
    user_id: int
    paper_id: int
    frequency: str
    weekday: int
    day_of_month: int
    start_date: date
    end_date: date

class SubscriptionWithNames(SubscriptionBase):
    id: int
    paper_name: str
    user_name: str
    class Config:
        from_attributes = True