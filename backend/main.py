"""
main.py — Main Learn2Lead FastAPI Application.
Plug in Module 1, Module 2, and Module 3 routers below when merging team ZIPs!
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import text

from .database import Base, engine, SessionLocal
from . import models  # noqa: F401 — ensures all 13 tables register with SQLAlchemy
from .seed import seed_initial_data
from .routers import auth

# 1. Create all PostgreSQL tables automatically if they don't exist
Base.metadata.create_all(bind=engine)

# 2. Seed starter Admin/Student accounts, Career Domains, and Readiness Weights
with SessionLocal() as db:
    seed_initial_data(db)

app = FastAPI(
    title="Learn2Lead — Student Study Planner & Career Readiness API",
    description="Modular FastAPI backend connected to Neon PostgreSQL.",
    version="1.0.0",
)

# --- CORE ROUTERS (Always Active) ---
app.include_router(auth.router)

# --- ADMIN CONTROL CENTER (User Account Management & Platform Metrics) ---
from .routers import admin
app.include_router(admin.router)

# ==============================================================================
# TEAM MODULE PLUG-IN SLOTS (Uncomment these lines after extracting module ZIPs)
# ==============================================================================
# --- MODULE 1 (Member 1: Academics — Study Planner, Quizzes, Analytics) ---
from .routers import academics
app.include_router(academics.router)

# --- MODULE 2 (Member 2: Employability, Career Roadmaps & Placement Score) ---
from .routers import employability
app.include_router(employability.router)

# --- MODULE 3 (Member 3: AI Recommender, Job Market Trends & Admin Panel) ---
from .routers import admin_insights
app.include_router(admin_insights.router)
# ==============================================================================


@app.get("/api/health", tags=["System"])
def health_check():
    """Verifies both FastAPI and Neon PostgreSQL are connected and healthy."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "PostgreSQL Connected", "app": "Learn2Lead"}


# --- Serve Frontend HTML, Tailwind CSS, JS, and Assets ---
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def serve_index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/dashboard")
def serve_student_dashboard():
    return FileResponse(str(FRONTEND_DIR / "dashboard.html"))


@app.get("/employability")
def serve_employability_page():
    return FileResponse(str(FRONTEND_DIR / "employability" / "career.html"))


@app.get("/leadership")
def serve_leadership_page():
    return FileResponse(str(FRONTEND_DIR / "leadership" / "leadership.html"))


@app.get("/admin")
def serve_admin_dashboard():
    return FileResponse(str(FRONTEND_DIR / "admin.html"))


@app.get("/admin-login")
def serve_admin_login():
    for filename in ("admin_login.html", "admin-login.html"):
        candidate = FRONTEND_DIR / filename
        if candidate.exists():
            return FileResponse(str(candidate))
    return {"error": f"Create admin_login.html inside {FRONTEND_DIR} and refresh."}