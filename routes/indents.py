from fastapi import APIRouter,HTTPException, BackgroundTasks, Body
from sqlmodel import Session, select
from database import engine
from models import Subscription, Paper, Exclusion, PaperPrice, Frequency, User
from typing import Dict
from datetime import date as date
from pydantic import BaseModel
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from fastapi.responses import StreamingResponse
from reportlab.platypus import PageBreak
from collections import defaultdict
import pandas as pd
from typing import List
from config import config


class IndentPDFRequest(BaseModel):
    date: str
    indent: Dict[str, int]

class IndentItem(BaseModel):
    apt_name: str
    paper: str
    block: str
    quantity: int

class PaperItem(BaseModel):
    paper: str
    quantity: int

class IndentPDFPayload(BaseModel):
    date: str
    indent: List[IndentItem]
    papers: List[PaperItem]

router = APIRouter()

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

@router.get("/")
def get_indent(date_str: str = None):
    from datetime import date
    if date_str:
        target = date.fromisoformat(date_str)
    else:
        from datetime import date, timedelta
        target = date.fromordinal(date.today().toordinal() + 1)
    with Session(engine) as s:
        subs = (
            s.query(
                Subscription.id,
                Subscription.paper_id,
                Subscription.day_of_month,
                Subscription.user_id,
                Subscription.frequency,
                Subscription.weekday,
                Subscription.start_date,
                Subscription.end_date,
                Paper.name.label("paper_name"),
                User.name.label("user_name"),
                User.flat_id.label("flat_id"),
                User.apt_name.label("apt_name")
            )
            .join(Paper, Paper.id == Subscription.paper_id)
            .join(User,User.id == Subscription.user_id)
            .all()
        )
        papers = []
        for sub in subs:
            if subscription_applies_on(sub, target) and not is_excluded(s, sub.user_id, sub.paper_id, target):
                papers.append({"paper":sub.paper_name,"apt_name": sub.apt_name, 'block':sub.flat_id[0], "quantity": 1})
        indents = pd.DataFrame(papers).groupby(['paper','apt_name','block'], as_index=False)['quantity'].sum()
    return {"date": target.isoformat(), "indent": indents.to_dict(orient='records'),"papers":indents.groupby(["paper"],as_index=False)['quantity'].sum().to_dict(orient='records')}

@router.post("/pdf")
def generate_indents_pdf(payload: IndentPDFPayload = Body(...)):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    elements.append(Paragraph(f"Indents and Papers Report - Date: {payload.date}", styles['Title']))
    elements.append(Spacer(1, 12))

    # 1️⃣ Papers Summary Table
    elements.append(Paragraph("Papers Summary", styles['Heading2']))
    paper_data = [["Paper", "Quantity"]]
    for p in payload.papers:
        paper_data.append([p.paper, str(p.quantity)])

    paper_table = Table(paper_data, hAlign='LEFT')
    paper_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ]))
    elements.append(paper_table)
    elements.append(Spacer(1, 24))

    # 2️⃣ Indent Details Table
    elements.append(Paragraph("Indent Details", styles['Heading2']))

    grouped_by_apt_block = defaultdict(list)
    for ind in payload.indent:
        grouped_by_apt_block[(ind.apt_name, ind.block)].append(ind)

    for idx, ((apt, block), rows) in enumerate(grouped_by_apt_block.items()):
        if idx > 0:  # Page break before all but first
            elements.append(PageBreak())

        # Subheading for each apartment+block
        elements.append(Paragraph(f"Apartment: {apt} - Block: {block}", styles['Heading3']))

        # Table for that apartment+block's indents
        table_data = [["Paper", "Quantity"]]
        for r in rows:
            table_data.append([r.paper, str(r.quantity)])

        table = Table(table_data, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('ALIGN', (1,1), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ]))
        elements.append(table)

    # Build PDF
    doc.build(elements)
    buffer.seek(0)

    return StreamingResponse(buffer, media_type='application/pdf', headers={
        "Content-Disposition": f"inline; filename=indents_{payload.date}.pdf"
    })