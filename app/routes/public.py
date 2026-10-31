import json
from datetime import datetime
from fastapi import APIRouter, Request, Query, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from app.db import get_db_connection
from app.i18n import t, get_lang_from_request, SUPPORTED_LANGUAGES

router = APIRouter()

def format_date_str(iso_date: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime("%d %b %Y")
    except Exception:
        return iso_date

@router.get("/favicon.ico")
async def favicon():
    # Return minimal SVG balance scale icon
    svg_icon = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="48" fill="#047857"/><text x="50" y="66" font-size="50" text-anchor="middle" fill="#ffffff" font-family="sans-serif">&#9878;</text></svg>'
    return Response(content=svg_icon, media_type="image/svg+xml")

@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    templates = request.app.state.templates
    lang = get_lang_from_request(request)
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get categories and count
    cursor.execute("SELECT category, COUNT(*) as cnt FROM services GROUP BY category ORDER BY cnt DESC")
    category_counts = [dict(row) for row in cursor.fetchall()]

    # Get 6 featured services
    cursor.execute("SELECT * FROM services ORDER BY id ASC LIMIT 6")
    featured_services = []
    for r in cursor.fetchall():
        item = dict(r)
        item["formatted_date"] = format_date_str(item["last_reviewed"])
        featured_services.append(item)

    # Get 4 recent FAQs
    cursor.execute("SELECT * FROM faqs ORDER BY id ASC LIMIT 4")
    featured_faqs = []
    for r in cursor.fetchall():
        item = dict(r)
        item["formatted_date"] = format_date_str(item["last_reviewed"])
        featured_faqs.append(item)

    conn.close()

    return templates.TemplateResponse(request=request, name="index.html", context={
        "lang": lang,
        "category_counts": category_counts,
        "featured_services": featured_services,
        "featured_faqs": featured_faqs,
        "t": t
    })

@router.get("/services", response_class=HTMLResponse)
async def services_directory(
    request: Request,
    category: str = Query(None),
    q: str = Query(None)
):
    templates = request.app.state.templates
    lang = get_lang_from_request(request)
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get distinct categories for filter chips
    cursor.execute("SELECT DISTINCT category FROM services ORDER BY category ASC")
    all_categories = [r["category"] for r in cursor.fetchall()]

    sql = "SELECT * FROM services WHERE 1=1"
    params = []

    if category and category.strip():
        sql += " AND category = ?"
        params.append(category.strip())

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        sql += " AND (name_en LIKE ? OR name_hi LIKE ? OR name_te LIKE ? OR desc_en LIKE ? OR department LIKE ? OR category LIKE ?)"
        params.extend([search_term, search_term, search_term, search_term, search_term, search_term])

    sql += " ORDER BY id ASC"
    cursor.execute(sql, params)

    services_list = []
    for r in cursor.fetchall():
        item = dict(r)
        item["formatted_date"] = format_date_str(item["last_reviewed"])
        services_list.append(item)

    conn.close()

    return templates.TemplateResponse(request=request, name="services.html", context={
        "lang": lang,
        "services": services_list,
        "all_categories": all_categories,
        "selected_category": category or "",
        "search_query": q or "",
        "t": t
    })

@router.get("/services/{identifier}", response_class=HTMLResponse)
async def service_detail(request: Request, identifier: str):
    templates = request.app.state.templates
    lang = get_lang_from_request(request)
    conn = get_db_connection()
    cursor = conn.cursor()

    # Match by slug or id
    if identifier.isdigit():
        cursor.execute("SELECT * FROM services WHERE id = ?", (int(identifier),))
    else:
        cursor.execute("SELECT * FROM services WHERE slug = ?", (identifier,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Service not found")

    service = dict(row)
    try:
        service["documents_list"] = json.loads(service.get("documents_json", "[]"))
    except Exception:
        service["documents_list"] = []

    try:
        service["steps_list"] = json.loads(service.get("steps_json", "[]"))
    except Exception:
        service["steps_list"] = []

    service["formatted_date"] = format_date_str(service["last_reviewed"])

    return templates.TemplateResponse(request=request, name="service_detail.html", context={
        "lang": lang,
        "service": service,
        "t": t
    })

@router.get("/faqs", response_class=HTMLResponse)
async def faqs_page(request: Request, q: str = Query(None)):
    templates = request.app.state.templates
    lang = get_lang_from_request(request)
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = "SELECT * FROM faqs WHERE 1=1"
    params = []
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        sql += " AND (question_en LIKE ? OR question_hi LIKE ? OR question_te LIKE ? OR answer_en LIKE ? OR answer_hi LIKE ? OR answer_te LIKE ? OR category LIKE ?)"
        params.extend([search_term, search_term, search_term, search_term, search_term, search_term, search_term])

    sql += " ORDER BY category ASC, id ASC"
    cursor.execute(sql, params)

    grouped_faqs = {}
    for r in cursor.fetchall():
        item = dict(r)
        item["formatted_date"] = format_date_str(item["last_reviewed"])
        cat = item["category"]
        if cat not in grouped_faqs:
            grouped_faqs[cat] = []
        grouped_faqs[cat].append(item)

    conn.close()

    return templates.TemplateResponse(request=request, name="faqs.html", context={
        "lang": lang,
        "grouped_faqs": grouped_faqs,
        "search_query": q or "",
        "t": t
    })

@router.post("/set-language")
async def set_language(request: Request):
    form = await request.form()
    lang = form.get("lang", "en")
    redirect_url = form.get("redirect_url") or request.headers.get("referer") or "/"

    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"

    response = RedirectResponse(url=redirect_url, status_code=303)
    response.set_cookie(key="lang", value=lang, max_age=30*24*3600, httponly=False, samesite="lax")
    return response
