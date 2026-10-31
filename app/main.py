from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import HTMLResponse

from app.auth import SECRET_KEY
from app.db import DB_PATH, init_db, seed_data
from app.retrieval import get_retriever
from app.i18n import t, get_lang_from_request

from app.routes.public import router as public_router
from app.routes.chat import router as chat_router
from app.routes.grievance import router as grievance_router
from app.routes.citizen import router as citizen_router
from app.routes.admin import router as admin_router

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

import os
if os.getenv("VERCEL"):
    UPLOADS_DIR = Path("/tmp/uploads")
else:
    UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Initialize DB & Seed Sample Data if not already present
try:
    if not DB_PATH.exists():
        init_db()
        seed_data()
        get_retriever()
except Exception:
    pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB & Seed Sample Data
    init_db()
    seed_data()
    # Warm up retrieval index
    get_retriever()
    yield

app = FastAPI(
    title="Public Grievance AI Assistant",
    description="Student-Hackathon Prototype (HACK-P438) for Civic Services Discovery & Grievance Redressal",
    version="1.0.0",
    lifespan=lifespan
)

# Starlette SessionMiddleware
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="grievance_session",
    max_age=14 * 24 * 3600,
    same_site="lax"
)

# Mount Static Files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Initialize Jinja2 Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)
# Add translation helper to templates environment
templates.env.globals["t"] = t
templates.env.globals["get_lang_from_request"] = get_lang_from_request
app.state.templates = templates

# Register Route Handlers
app.include_router(public_router)
app.include_router(chat_router)
app.include_router(grievance_router)
app.include_router(citizen_router)
app.include_router(admin_router)

# Custom Error Handlers
@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    lang = get_lang_from_request(request)
    return templates.TemplateResponse(
        request=request,
        name="404.html",
        context={
            "lang": lang,
            "t": t
        },
        status_code=404
    )

@app.exception_handler(403)
async def custom_403_handler(request: Request, exc):
    lang = get_lang_from_request(request)
    detail_msg = getattr(exc, "detail", "Access Forbidden")
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html lang="{lang}">
        <head><title>403 Forbidden</title><link rel="stylesheet" href="/static/css/style.css"></head>
        <body style="padding: 40px; text-align: center;">
          <div class="card" style="max-width: 500px; margin: 40px auto; padding: 32px;">
            <h1 style="color: #991b1b;">403 - Access Forbidden</h1>
            <p>{detail_msg}</p>
            <a href="/login" class="btn btn-primary" style="margin-top: 16px;">Sign In</a>
            <a href="/" class="btn btn-outline" style="margin-top: 16px;">Home</a>
          </div>
        </body>
        </html>
        """,
        status_code=403
    )

@app.exception_handler(429)
async def custom_429_handler(request: Request, exc):
    lang = get_lang_from_request(request)
    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html lang="{lang}">
        <head><title>429 Too Many Requests</title><link rel="stylesheet" href="/static/css/style.css"></head>
        <body style="padding: 40px; text-align: center;">
          <div class="card" style="max-width: 500px; margin: 40px auto; padding: 32px;">
            <h1 style="color: #c05621;">429 - Rate Limit Exceeded</h1>
            <p>Maximum 20 requests per minute allowed. Please wait 60 seconds before retrying.</p>
            <a href="/" class="btn btn-primary" style="margin-top: 16px;">Home</a>
          </div>
        </body>
        </html>
        """,
        status_code=429
    )
