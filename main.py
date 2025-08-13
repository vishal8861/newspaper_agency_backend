from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, create_db_and_tables
from routes import users, papers, subscriptions, exclusions, indents, billing,bill_payment_status

app = FastAPI(title="Newspaper Agency API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(papers.router, prefix="/papers", tags=["papers"])
app.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
app.include_router(exclusions.router, prefix="/exclusions", tags=["exclusions"])
app.include_router(indents.router, prefix="/indents", tags=["indents"])
app.include_router(billing.router, prefix="/billing", tags=["billing"])
app.include_router(bill_payment_status.router, prefix="/payment", tags=["billing"])

app.route("/health")
def health():
    return {"status":"up"}

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
