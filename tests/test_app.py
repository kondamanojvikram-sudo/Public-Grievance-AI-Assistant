import io
import pytest
from pathlib import Path
from starlette.testclient import TestClient

from app.main import app
from app.db import init_db, seed_data, get_db_connection

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    init_db()
    seed_data()

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

# 1. Pages return 200
def test_pages_return_200(client):
    endpoints = ["/", "/services", "/faqs", "/chat", "/grievance/new", "/track", "/login", "/register"]
    for path in endpoints:
        response = client.get(path)
        assert response.status_code == 200, f"Expected 200 for {path}, got {response.status_code}"
        assert "Prototype with sample data" in response.text

# 2. Service count >= 15
def test_service_count_ge_15(client):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM services")
    count = cursor.fetchone()["cnt"]
    conn.close()
    assert count >= 15, f"Expected at least 15 services, found {count}"

# 3. Search works
def test_services_search_works(client):
    # Search for 'water'
    resp = client.get("/services?q=water")
    assert resp.status_code == 200
    assert "water" in resp.text.lower()

    # Search for 'birth'
    resp_birth = client.get("/services?q=birth")
    assert resp_birth.status_code == 200
    assert "birth" in resp_birth.text.lower()

# 4. Supported chat question returns sources and confidence
def test_chat_supported_question(client):
    payload = {
        "message": "What documents do I need for a birth certificate?",
        "language": "en"
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence"] in ["high", "medium"]
    assert len(data["sources"]) >= 1
    assert "birth certificate" in data["sources"][0]["title"].lower()
    assert "disclaimer" not in data["answer"].lower() or "guidance" in data["answer"].lower()

# 5. Unsupported question returns low confidence and NO fabricated source
def test_chat_unsupported_question(client):
    payload = {
        "message": "Will I win my court case?",
        "language": "en"
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["confidence"] == "low"
    assert len(data["sources"]) == 0
    assert "cannot answer" in data["answer"].lower()

# 6. Bad grievance input rejected (validation fails)
def test_bad_grievance_input_rejected(client):
    # Missing subject (too short) and description too short
    # First get csrf token from form
    get_resp = client.get("/grievance/new")
    assert get_resp.status_code == 200

    csrf_token = client.cookies.get("grievance_session") # session is established
    # Send empty or bad form data
    form_data = {
        "csrf_token": "invalid_or_missing",
        "category": "InvalidCategory",
        "subject": "Hi",  # < 5 chars
        "description": "Short",  # < 20 chars
        "area": "Invalid Area"
    }
    resp = client.post("/grievance/new", data=form_data)
    # CSRF or validation failure
    assert resp.status_code in [400, 403]

# 7. Valid submission gives unique reference and status history row
def test_valid_grievance_submission(client):
    # Fetch new form to get valid CSRF from session
    get_resp = client.get("/grievance/new")
    assert get_resp.status_code == 200

    # Extract csrf token from html
    import re
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', get_resp.text)
    assert match is not None
    csrf_token = match.group(1)

    form_data = {
        "csrf_token": csrf_token,
        "category": "Municipal",
        "subject": "Deep pothole outside community center gate",
        "description": "A very large hazardous pothole has formed outside the community center gate causing two-wheeler accidents.",
        "area": "Ward 07 - Subhash Nagar",
        "landmark": "Near Community Hall Gate 2",
        "name": "Pooja Sharma",
        "contact": "pooja@test.mail"
    }

    resp = client.post("/grievance/new", data=form_data, follow_redirects=False)
    assert resp.status_code == 303
    redirect_url = resp.headers["location"]
    assert "/grievance/confirm/GRV-" in redirect_url

    ref = redirect_url.split("/")[-1]

    # Verify database insertion
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM grievances WHERE reference = ?", (ref,))
    row = cursor.fetchone()
    assert row is not None
    assert row["subject"] == form_data["subject"]
    assert row["status"] == "Submitted"

    # Verify status history row exists
    cursor.execute("SELECT * FROM status_history WHERE grievance_id = ?", (row["id"],))
    hist = cursor.fetchall()
    assert len(hist) >= 1
    assert hist[0]["status"] == "Submitted"
    conn.close()

# 8. /track works
def test_track_page_lookup(client):
    # Look up seeded reference GRV-2026-000101
    resp = client.get("/track?ref=GRV-2026-000101")
    assert resp.status_code == 200
    assert "GRV-2026-000101" in resp.text
    assert "Water Supply" in resp.text
    assert "Status Timeline" in resp.text

# 9. Non-staff blocked from /admin
def test_non_staff_blocked_from_admin(client):
    # Anonymous request
    resp = client.get("/admin", follow_redirects=False)
    assert resp.status_code == 303  # redirects to /login

    # Login as citizen
    get_login = client.get("/login")
    import re
    token = re.search(r'name="csrf_token"\s+value="([^"]+)"', get_login.text).group(1)
    login_resp = client.post("/login", data={
        "csrf_token": token,
        "email": "citizen@demo.test",
        "password": "Citizen@123"
    }, follow_redirects=False)
    assert login_resp.status_code == 303
    assert login_resp.headers["location"] == "/dashboard"

    # Citizen tries to access /admin -> 403 Forbidden!
    admin_resp = client.get("/admin")
    assert admin_resp.status_code == 403

# 10. Staff status update appends history
def test_staff_status_update_appends_history(client):
    # Login as staff
    get_login = client.get("/login")
    import re
    token = re.search(r'name="csrf_token"\s+value="([^"]+)"', get_login.text).group(1)
    login_resp = client.post("/login", data={
        "csrf_token": token,
        "email": "staff@demo.test",
        "password": "Staff@123"
    }, follow_redirects=False)
    assert login_resp.status_code == 303
    assert login_resp.headers["location"] == "/admin"

    # Staff accesses /admin
    admin_resp = client.get("/admin")
    assert admin_resp.status_code == 200
    assert "Staff Grievance Queue" in admin_resp.text

    # Detail page of grievance id 1
    detail_resp = client.get("/admin/grievance/1")
    assert detail_resp.status_code == 200
    detail_token = re.search(r'name="csrf_token"\s+value="([^"]+)"', detail_resp.text).group(1)

    # Perform status update
    update_data = {
        "csrf_token": detail_token,
        "new_status": "Resolved",
        "new_priority": "High",
        "new_category": "Water Supply",
        "staff_note": "Repairs completed by maintenance crew; water flow restored."
    }
    update_resp = client.post("/admin/grievance/1", data=update_data, follow_redirects=False)
    assert update_resp.status_code == 303

    # Check status history has appended new row
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM grievances WHERE id = 1")
    g = cursor.fetchone()
    assert g["status"] == "Resolved"

    cursor.execute("SELECT * FROM status_history WHERE grievance_id = 1 ORDER BY id DESC")
    last_hist = cursor.fetchone()
    assert last_hist["status"] == "Resolved"
    assert "Repairs completed" in last_hist["note"]
    conn.close()

# 11. Bad upload rejected
def test_bad_upload_rejected(client):
    get_resp = client.get("/grievance/new")
    import re
    csrf_token = re.search(r'name="csrf_token"\s+value="([^"]+)"', get_resp.text).group(1)

    # Attempt to upload an illegal executable file (.exe)
    fake_file = io.BytesIO(b"Fake executable content")
    files = {
        "attachment": ("exploit.exe", fake_file, "application/octet-stream")
    }
    form_data = {
        "csrf_token": csrf_token,
        "category": "Municipal",
        "subject": "Testing file validation rejection",
        "description": "Detailed explanation that is long enough to satisfy twenty characters constraint.",
        "area": "Ward 02 - Rajendra Nagar"
    }

    resp = client.post("/grievance/new", data=form_data, files=files)
    assert resp.status_code == 400
    assert "Invalid file type" in resp.text
