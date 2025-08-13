from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import date
from enum import Enum

class Frequency(str, Enum):
    DAILY = 'daily'
    WEEKLY = 'weekly'
    MONTHLY = 'monthly'
    ALTERNATING = 'alternating'

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    mobile: str
    flat_id: str
    apt_name: str

class Paper(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str

class PaperPrice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    paper_id: int = Field(foreign_key="paper.id")
    day_of_week: Optional[int] = None
    price: float

class PaperPriceView(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    paper_id: int = Field(foreign_key="paper.id")
    day_of_week: Optional[int] = None
    price: float

class Subscription(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    paper_id: int = Field(foreign_key="paper.id")
    frequency: Frequency
    weekday: Optional[int] = None
    day_of_month: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class Exclusion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    paper_id: Optional[int] = Field(foreign_key="paper.id")
    date_from: date
    date_to: date

class BillPaymentStatus(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", nullable=False)
    year: int
    month: int
    status: str
    amount_paid: float = 0.0
    balance: float = 0.0