from datetime import datetime, timezone
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth import (
    hash_password,
    verify_password,
    validate_csrf_token,
    generate_csrf_token,
    get_session_user
)
from app.db import get_db_connection
from app.i18n import t, get_lang_from_request

router = APIRouter()

def format_date_str(iso_date: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return iso_date

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    templates = request.app.state.templates
    lang = get_lang_from_request(request)
    csrf_token = generate_csrf_token(request)
    user = get_session_user(request)

    if user:
        if user["role"] == "staff":
            return RedirectResponse(url="/admin", status_code=303)
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(request=request, name="login.html", context={
        "lang": lang,
        "csrf_token": csrf_token,
        "error": None,
        "t": t
    })

@router.post("/login", response_class=HTMLResponse)
async def login_action(
    request: Request,
    csrf_token: str = Form(""),
    email: str = Form(""),
    password: str = Form("")
):
    templates = request.app.state.templates
    lang = get_lang_from_request(request)

    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    email = email.strip().lower()
    password = password.strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user_row = cursor.fetchone()
    conn.close()

    if not user_row or not verify_password(password, user_row["salt"], user_row["password_hash"]):
        return templates.TemplateResponse(request=request, name="login.html", context={
            "lang": lang,
            "csrf_token": generate_csrf_token(request),
            "error": "Invalid email or password credentials. Please try again.",
            "t": t
        }, status_code=401)

    # Establish session
    request.session["user_id"] = user_row["id"]
    request.session["user_name"] = user_row["name"]
    request.session["user_email"] = user_row["email"]
    request.session["user_role"] = user_row["role"]

    if user_row["role"] == "staff":
        return RedirectResponse(url="/admin", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    templates = request.app.state.templates
    lang = get_lang_from_request(request)
    csrf_token = generate_csrf_token(request)
    user = get_session_user(request)

    if user:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(request=request, name="register.html", context={
        "lang": lang,
        "csrf_token": csrf_token,
        "error": None,
        "form_data": {},
        "t": t
    })

@router.post("/register", response_class=HTMLResponse)
async def register_action(
    request: Request,
    csrf_token: str = Form(""),
    name: str = Form(""),
    email: str = Form(""),
    password: str = Form(""),
    confirm_password: str = Form("")
):
    templates = request.app.state.templates
    lang = get_lang_from_request(request)

    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    name = name.strip()
    email = email.strip().lower()
    password = password.strip()
    confirm_password = confirm_password.strip()

    error = None
    if len(name) < 2:
        error = "Name must be at least 2 characters long."
    elif "@" not in email or "." not in email:
        error = "Please provide a valid email address."
    elif len(password) < 6:
        error = "Password must be at least 6 characters long."
    elif password != confirm_password:
        error = "Passwords do not match."

    if error:
        return templates.TemplateResponse(request=request, name="register.html", context={
            "lang": lang,
            "csrf_token": generate_csrf_token(request),
            "error": error,
            "form_data": {"name": name, "email": email},
            "t": t
        }, status_code=400)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return templates.TemplateResponse(request=request, name="register.html", context={
            "lang": lang,
            "csrf_token": generate_csrf_token(request),
            "error": "An account with this email address already exists. Please log in.",
            "form_data": {"name": name, "email": email},
            "t": t
        }, status_code=400)

    p_hash, salt = hash_password(password)
    now_str = datetime.now(timezone.utc).isoformat()

    cursor.execute("""
    INSERT INTO users (name, email, password_hash, salt, role, created_at)
    VALUES (?, ?, ?, ?, 'citizen', ?)
    """, (name, email, p_hash, salt, now_str))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    request.session["user_id"] = user_id
    request.session["user_name"] = name
    request.session["user_email"] = email
    request.session["user_role"] = "citizen"

    return RedirectResponse(url="/dashboard", status_code=303)

@router.get("/logout")
async def logout_action(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)

@router.get("/dashboard", response_class=HTMLResponse)
async def citizen_dashboard(request: Request, ref: str = None):
    templates = request.app.state.templates
    lang = get_lang_from_request(request)
    user = get_session_user(request)

    if not user:
        return RedirectResponse(url="/login", status_code=303)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch grievances belonging to this user
    cursor.execute("""
    SELECT * FROM grievances WHERE user_id = ? ORDER BY id DESC
    """, (user["id"],))

    user_grievances = []
    for row in cursor.fetchall():
        item = dict(row)
        item["formatted_created"] = format_date_str(item["created_at"])
        item["formatted_updated"] = format_date_str(item["updated_at"])
        user_grievances.append(item)

    selected_grievance = None
    selected_history = []
    if ref:
        cursor.execute("SELECT * FROM grievances WHERE reference = ? AND user_id = ?", (ref, user["id"]))
        s_row = cursor.fetchone()
        if s_row:
            selected_grievance = dict(s_row)
            selected_grievance["formatted_created"] = format_date_str(selected_grievance["created_at"])
            selected_grievance["formatted_updated"] = format_date_str(selected_grievance["updated_at"])
            cursor.execute("""
            SELECT * FROM status_history WHERE grievance_id = ? ORDER BY changed_at ASC
            """, (selected_grievance["id"],))
            for h in cursor.fetchall():
                h_item = dict(h)
                h_item["formatted_time"] = format_date_str(h_item["changed_at"])
                selected_history.append(h_item)

    conn.close()

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "lang": lang,
        "user": user,
        "grievances": user_grievances,
        "selected_grievance": selected_grievance,
        "selected_history": selected_history,
        "t": t
    })
