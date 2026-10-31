from datetime import datetime, timezone
from fastapi import APIRouter, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth import get_session_user, validate_csrf_token, generate_csrf_token
from app.db import get_db_connection
from app.i18n import t, get_lang_from_request
from app.routes.grievance import SAMPLE_WARDS, CIVIC_CATEGORIES

router = APIRouter()

VALID_STATUSES = ["Submitted", "Under Review", "In Progress", "Resolved", "Rejected"]
VALID_PRIORITIES = ["Low", "Medium", "High"]

def format_date_str(iso_date: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return iso_date

@router.get("/admin", response_class=HTMLResponse)
async def admin_queue(
    request: Request,
    status: str = Query(None),
    category: str = Query(None),
    area: str = Query(None),
    q: str = Query(None),
    sort: str = Query("date_desc"),
    page: int = Query(1, ge=1)
):
    templates = request.app.state.templates
    lang = get_lang_from_request(request)
    user = get_session_user(request)

    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user["role"] != "staff":
        raise HTTPException(status_code=403, detail="Forbidden: Staff privileges required to access the admin queue.")

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Analytics counts for CSS bars
    cursor.execute("SELECT status, COUNT(*) as cnt FROM grievances GROUP BY status")
    status_counts = {r["status"]: r["cnt"] for r in cursor.fetchall()}
    total_grievances = sum(status_counts.values()) or 1

    cursor.execute("SELECT category, COUNT(*) as cnt FROM grievances GROUP BY category ORDER BY cnt DESC")
    category_counts = [dict(r) for r in cursor.fetchall()]

    # 2. Query grievances with filters
    sql = "SELECT * FROM grievances WHERE 1=1"
    params = []

    if status and status in VALID_STATUSES:
        sql += " AND status = ?"
        params.append(status)

    if category and category in CIVIC_CATEGORIES:
        sql += " AND category = ?"
        params.append(category)

    if area and area in SAMPLE_WARDS:
        sql += " AND area = ?"
        params.append(area)

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        sql += " AND (reference LIKE ? OR subject LIKE ? OR description LIKE ? OR name LIKE ?)"
        params.extend([search_term, search_term, search_term, search_term])

    # Sorting
    if sort == "date_asc":
        sql += " ORDER BY id ASC"
    elif sort == "priority":
        sql += " ORDER BY CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 3 ELSE 4 END, id DESC"
    else:  # date_desc
        sql += " ORDER BY id DESC"

    # Count total matching rows
    count_sql = f"SELECT COUNT(*) as total FROM ({sql})"
    cursor.execute(count_sql, params)
    total_matching = cursor.fetchone()["total"]

    # Pagination: 10 per page
    per_page = 10
    total_pages = max(1, (total_matching + per_page - 1) // per_page)
    offset = (page - 1) * per_page

    paged_sql = sql + f" LIMIT {per_page} OFFSET {offset}"
    cursor.execute(paged_sql, params)

    grievance_items = []
    for r in cursor.fetchall():
        item = dict(r)
        item["formatted_created"] = format_date_str(item["created_at"])
        item["formatted_updated"] = format_date_str(item["updated_at"])
        grievance_items.append(item)

    conn.close()

    return templates.TemplateResponse(request=request, name="admin_queue.html", context={
        "lang": lang,
        "user": user,
        "grievances": grievance_items,
        "status_counts": status_counts,
        "category_counts": category_counts,
        "total_grievances": total_grievances,
        "valid_statuses": VALID_STATUSES,
        "categories": CIVIC_CATEGORIES,
        "wards": SAMPLE_WARDS,
        "current_status": status or "",
        "current_category": category or "",
        "current_area": area or "",
        "search_query": q or "",
        "current_sort": sort,
        "current_page": page,
        "total_pages": total_pages,
        "total_matching": total_matching,
        "t": t
    })

@router.get("/admin/grievance/{grievance_id}", response_class=HTMLResponse)
async def admin_detail(request: Request, grievance_id: int):
    templates = request.app.state.templates
    lang = get_lang_from_request(request)
    user = get_session_user(request)

    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user["role"] != "staff":
        raise HTTPException(status_code=403, detail="Forbidden: Staff privileges required.")

    csrf_token = generate_csrf_token(request)
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM grievances WHERE id = ?", (grievance_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Grievance not found")

    grievance = dict(row)
    grievance["formatted_created"] = format_date_str(grievance["created_at"])
    grievance["formatted_updated"] = format_date_str(grievance["updated_at"])

    cursor.execute("SELECT * FROM status_history WHERE grievance_id = ? ORDER BY changed_at ASC", (grievance_id,))
    history = []
    for h in cursor.fetchall():
        h_dict = dict(h)
        h_dict["formatted_time"] = format_date_str(h_dict["changed_at"])
        history.append(h_dict)

    conn.close()

    return templates.TemplateResponse(request=request, name="admin_detail.html", context={
        "lang": lang,
        "user": user,
        "grievance": grievance,
        "history": history,
        "csrf_token": csrf_token,
        "valid_statuses": VALID_STATUSES,
        "valid_priorities": VALID_PRIORITIES,
        "categories": CIVIC_CATEGORIES,
        "t": t
    })

@router.post("/admin/grievance/{grievance_id}", response_class=HTMLResponse)
async def admin_update_grievance(
    request: Request,
    grievance_id: int,
    csrf_token: str = Form(""),
    new_status: str = Form(""),
    new_priority: str = Form(""),
    new_category: str = Form(""),
    staff_note: str = Form("")
):
    user = get_session_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user["role"] != "staff":
        raise HTTPException(status_code=403, detail="Forbidden: Staff privileges required.")

    if not validate_csrf_token(request, csrf_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM grievances WHERE id = ?", (grievance_id,))
    current = cursor.fetchone()
    if not current:
        conn.close()
        raise HTTPException(status_code=404, detail="Grievance not found")

    status = new_status if new_status in VALID_STATUSES else current["status"]
    priority = new_priority if new_priority in VALID_PRIORITIES else current["priority"]
    category = new_category if new_category in CIVIC_CATEGORIES else current["category"]
    note = staff_note.strip() if staff_note else f"Status updated to '{status}' by staff"

    now_str = datetime.now(timezone.utc).isoformat()

    # Update grievance
    cursor.execute("""
    UPDATE grievances
    SET status = ?, priority = ?, category = ?, updated_at = ?
    WHERE id = ?
    """, (status, priority, category, now_str, grievance_id))

    # Append to status_history
    cursor.execute("""
    INSERT INTO status_history (grievance_id, status, note, changed_by, changed_at)
    VALUES (?, ?, ?, ?, ?)
    """, (grievance_id, status, note, f"Staff ({user['name']})", now_str))

    conn.commit()
    conn.close()

    return RedirectResponse(url=f"/admin/grievance/{grievance_id}", status_code=303)
