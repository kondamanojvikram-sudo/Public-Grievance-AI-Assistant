import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from app.auth import (
    validate_csrf_token,
    generate_csrf_token,
    check_rate_limit,
    get_session_user
)
from app.db import get_db_connection
from app.i18n import t, get_lang_from_request

router = APIRouter()

if os.getenv("VERCEL"):
    UPLOAD_DIR = Path("/tmp/uploads")
else:
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", Path(__file__).resolve().parent.parent / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2 MB

SAMPLE_WARDS = [
    "Ward 01 - Secretariat & Civil Lines",
    "Ward 02 - Rajendra Nagar",
    "Ward 03 - Market Yard",
    "Ward 04 - Industrial Estate",
    "Ward 05 - Old City & Heritage",
    "Ward 06 - Ambedkar Colony",
    "Ward 07 - Subhash Nagar",
    "Ward 08 - Railway Colony",
    "Ward 09 - Ashok Nagar",
    "Ward 10 - Lake View Enclave",
    "Ward 11 - University Campus Area",
    "Ward 12 - Gandhinagar",
    "Ward 13 - Balaji Hills",
    "Ward 14 - Nehru Nagar",
    "Ward 15 - Shanti Nagar",
    "Ward 16 - Greenfield Extension",
    "Ward 17 - Port & Logistics Area",
    "Ward 18 - Ring Road & Tech Zone"
]

CIVIC_CATEGORIES = [
    "Municipal",
    "Water Supply",
    "Electricity",
    "Transport",
    "Revenue & Land",
    "Police Non-Emergency",
    "Food & Civil Supplies",
    "Social Welfare & Pensions",
    "Health",
    "Education"
]

def format_date_str(iso_date: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return iso_date

def generate_reference(cursor) -> str:
    year = datetime.now(timezone.utc).year
    cursor.execute("SELECT MAX(id) as max_id FROM grievances")
    row = cursor.fetchone()
    next_id = (row["max_id"] or 100) + 1
    return f"GRV-{year}-{next_id:06d}"

def check_duplicate_grievance(cursor, category: str, area: str, subject: str) -> str | None:
    # Check if a grievance with identical category and area was created in the last 7 days
    words = [w.lower() for w in subject.split() if len(w) > 3]
    cursor.execute("""
        SELECT reference, subject FROM grievances
        WHERE category = ? AND area = ?
        ORDER BY id DESC LIMIT 5
    """, (category, area))
    for r in cursor.fetchall():
        prev_sub = r["subject"].lower()
        # count shared significant words
        common = [w for w in words if w in prev_sub]
        if len(common) >= 2 or subject.lower() in prev_sub:
            return r["reference"]
    return None

@router.get("/grievance/new", response_class=HTMLResponse)
async def grievance_form(request: Request):
    templates = request.app.state.templates
    lang = get_lang_from_request(request)
    csrf_token = generate_csrf_token(request)
    user = get_session_user(request)

    return templates.TemplateResponse(request=request, name="grievance_new.html", context={
        "lang": lang,
        "csrf_token": csrf_token,
        "user": user,
        "categories": CIVIC_CATEGORIES,
        "wards": SAMPLE_WARDS,
        "errors": {},
        "form_data": {},
        "similar_ref": None,
        "t": t
    })

@router.post("/grievance/new", response_class=HTMLResponse)
async def submit_grievance(
    request: Request,
    csrf_token: str = Form(""),
    category: str = Form(""),
    subject: str = Form(""),
    description: str = Form(""),
    area: str = Form(""),
    landmark: str = Form(""),
    name: str = Form(""),
    contact: str = Form(""),
    attachment: UploadFile = File(None)
):
    templates = request.app.state.templates
    lang = get_lang_from_request(request)
    user = get_session_user(request)

    # 1. Rate Limiting: 20 req/min per IP
    if not check_rate_limit(request, prefix="submit", limit=20, window_seconds=60.0):
        raise HTTPException(
            status_code=429,
            detail="Too many submission requests. Please wait a minute before filing again."
        )

    # 2. CSRF Validation
    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or expired CSRF security token.")

    # 3. Server-side Validation
    errors = {}
    form_data = {
        "category": category,
        "subject": subject,
        "description": description,
        "area": area,
        "landmark": landmark,
        "name": name,
        "contact": contact
    }

    category = category.strip()
    if not category or category not in CIVIC_CATEGORIES:
        errors["category"] = "Please select a valid service category."

    subject = subject.strip()
    if len(subject) < 5 or len(subject) > 120:
        errors["subject"] = "Subject must be between 5 and 120 characters."

    description = description.strip()
    if len(description) < 20 or len(description) > 2000:
        errors["description"] = "Description must be between 20 and 2000 characters."

    area = area.strip()
    if not area or area not in SAMPLE_WARDS:
        errors["area"] = "Please select a valid municipal ward/area."

    # Validate attachment if present
    attachment_saved_path = None
    if attachment and attachment.filename:
        ext = Path(attachment.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            errors["attachment"] = f"Invalid file type {ext}. Only PDF, JPG, and PNG are allowed."
        else:
            contents = await attachment.read()
            if len(contents) > MAX_FILE_SIZE:
                errors["attachment"] = "File size exceeds the 2 MB limit."
            else:
                # Save under random UUID name
                unique_filename = f"{uuid.uuid4().hex}{ext}"
                target_file = UPLOAD_DIR / unique_filename
                with open(target_file, "wb") as f:
                    f.write(contents)
                attachment_saved_path = unique_filename

    if errors:
        return templates.TemplateResponse(request=request, name="grievance_new.html", context={
            "lang": lang,
            "csrf_token": generate_csrf_token(request),
            "user": user,
            "categories": CIVIC_CATEGORIES,
            "wards": SAMPLE_WARDS,
            "errors": errors,
            "form_data": form_data,
            "similar_ref": None,
            "t": t
        }, status_code=400)

    # 4. Save to Database
    conn = get_db_connection()
    cursor = conn.cursor()

    similar_ref = check_duplicate_grievance(cursor, category, area, subject)

    reference = generate_reference(cursor)
    now_str = datetime.now(timezone.utc).isoformat()
    user_id = user["id"] if user else None

    # Priority determination based on keywords
    priority = "Medium"
    lower_desc = f"{subject} {description}".lower()
    if any(k in lower_desc for k in ["emergency", "burst", "bursting", "electric shock", "danger", "flooding", "overflow", "fire", "urgent", "hazard"]):
        priority = "High"
    elif any(k in lower_desc for k in ["information", "query", "suggestion", "bus timetable", "general"]):
        priority = "Low"

    cursor.execute("""
    INSERT INTO grievances (
        reference, user_id, name, contact, subject, description,
        category, area, landmark, attachment_path, status, priority,
        created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Submitted', ?, ?, ?)
    """, (
        reference,
        user_id,
        name.strip() if name else None,
        contact.strip() if contact else None,
        subject,
        description,
        category,
        area,
        landmark.strip() if landmark else None,
        attachment_saved_path,
        priority,
        now_str,
        now_str
    ))
    g_id = cursor.lastrowid

    # Append initial status history
    cursor.execute("""
    INSERT INTO status_history (grievance_id, status, note, changed_by, changed_at)
    VALUES (?, 'Submitted', 'Grievance submitted via citizen web portal', 'System', ?)
    """, (g_id, now_str))

    conn.commit()
    conn.close()

    # Track this reference in session for anonymous creator access
    submitted_refs = request.session.get("submitted_refs", [])
    submitted_refs.append(reference)
    request.session["submitted_refs"] = submitted_refs

    if similar_ref:
        request.session["flash_warning"] = f"Notice: A similar grievance ({similar_ref}) was recently submitted for {area}. Your request has also been registered."

    return RedirectResponse(url=f"/grievance/confirm/{reference}", status_code=303)

@router.get("/grievance/confirm/{reference}", response_class=HTMLResponse)
async def grievance_confirmation(request: Request, reference: str):
    templates = request.app.state.templates
    lang = get_lang_from_request(request)
    warning_banner = request.session.pop("flash_warning", None)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM grievances WHERE reference = ?", (reference,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Grievance reference not found")

    grievance = dict(row)
    grievance["formatted_created"] = format_date_str(grievance["created_at"])

    return templates.TemplateResponse(request=request, name="grievance_confirm.html", context={
        "lang": lang,
        "grievance": grievance,
        "warning_banner": warning_banner,
        "t": t
    })

@router.get("/track", response_class=HTMLResponse)
async def track_page(request: Request, ref: str = ""):
    templates = request.app.state.templates
    lang = get_lang_from_request(request)

    grievance = None
    history = []
    error = None

    ref = ref.strip().upper()
    if ref:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM grievances WHERE reference = ?", (ref,))
        g_row = cursor.fetchone()
        if g_row:
            grievance = dict(g_row)
            grievance["formatted_created"] = format_date_str(grievance["created_at"])
            grievance["formatted_updated"] = format_date_str(grievance["updated_at"])

            cursor.execute("SELECT * FROM status_history WHERE grievance_id = ? ORDER BY changed_at ASC", (grievance["id"],))
            for h in cursor.fetchall():
                h_dict = dict(h)
                h_dict["formatted_time"] = format_date_str(h_dict["changed_at"])
                history.append(h_dict)
        else:
            error = f"No grievance record found with reference number '{ref}'."
        conn.close()

    return templates.TemplateResponse(request=request, name="track.html", context={
        "lang": lang,
        "ref": ref,
        "grievance": grievance,
        "history": history,
        "error": error,
        "t": t
    })

@router.get("/uploads/{filename}")
async def serve_upload(request: Request, filename: str):
    # Security: check filename has no path separators and is pure alphanumeric + allowed extension
    clean_name = os.path.basename(filename)
    if clean_name != filename:
        raise HTTPException(status_code=400, detail="Invalid file path.")

    file_path = UPLOAD_DIR / clean_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")

    # Access control: only staff or the owner can access
    user = get_session_user(request)
    is_staff = user and user["role"] == "staff"

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, reference FROM grievances WHERE attachment_path = ?", (clean_name,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="File attachment not found.")

    is_owner = False
    if user and row["user_id"] and user["id"] == row["user_id"]:
        is_owner = True
    elif row["reference"] in request.session.get("submitted_refs", []):
        is_owner = True

    if not (is_staff or is_owner):
        raise HTTPException(status_code=403, detail="Access denied. Only authorized staff and the submitter can view attachments.")

    return FileResponse(file_path, filename=clean_name)
