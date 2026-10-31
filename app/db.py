import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta
from app.auth import hash_password

if os.getenv("VERCEL"):
    DB_PATH = Path("/tmp/grievance.db")
else:
    DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).resolve().parent / "grievance.db"))
DATA_DIR = Path(__file__).parent / "data"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('citizen', 'staff')),
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL,
        category TEXT NOT NULL,
        department TEXT NOT NULL,
        name_en TEXT NOT NULL,
        name_hi TEXT NOT NULL,
        name_te TEXT NOT NULL,
        desc_en TEXT NOT NULL,
        desc_hi TEXT NOT NULL,
        desc_te TEXT NOT NULL,
        eligibility TEXT NOT NULL,
        documents_json TEXT NOT NULL,
        steps_json TEXT NOT NULL,
        fees TEXT NOT NULL,
        processing_time TEXT NOT NULL,
        source_name TEXT NOT NULL,
        source_url TEXT NOT NULL,
        last_reviewed TEXT NOT NULL,
        is_sample INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS faqs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        question_en TEXT NOT NULL,
        question_hi TEXT NOT NULL,
        question_te TEXT NOT NULL,
        answer_en TEXT NOT NULL,
        answer_hi TEXT NOT NULL,
        answer_te TEXT NOT NULL,
        source_name TEXT NOT NULL,
        source_url TEXT NOT NULL,
        last_reviewed TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS grievances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference TEXT UNIQUE NOT NULL,
        user_id INTEGER NULL,
        name TEXT,
        contact TEXT,
        subject TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        area TEXT NOT NULL,
        landmark TEXT,
        attachment_path TEXT NULL,
        status TEXT NOT NULL DEFAULT 'Submitted' CHECK(status IN ('Submitted', 'Under Review', 'In Progress', 'Resolved', 'Rejected')),
        priority TEXT NOT NULL DEFAULT 'Medium' CHECK(priority IN ('Low', 'Medium', 'High')),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grievance_id INTEGER NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('Submitted', 'Under Review', 'In Progress', 'Resolved', 'Rejected')),
        note TEXT,
        changed_by TEXT NOT NULL,
        changed_at TEXT NOT NULL,
        FOREIGN KEY (grievance_id) REFERENCES grievances(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_services_category ON services(category);
    CREATE INDEX IF NOT EXISTS idx_grievances_ref ON grievances(reference);
    CREATE INDEX IF NOT EXISTS idx_grievances_user ON grievances(user_id);
    CREATE INDEX IF NOT EXISTS idx_grievances_status ON grievances(status);
    CREATE INDEX IF NOT EXISTS idx_grievances_category ON grievances(category);
    CREATE INDEX IF NOT EXISTS idx_status_history_grievance ON status_history(grievance_id);
    """)

    conn.commit()
    conn.close()

def seed_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now(timezone.utc).isoformat()

    # 1. Seed demo users
    staff_email = "staff@demo.test"
    cursor.execute("SELECT id FROM users WHERE email = ?", (staff_email,))
    if not cursor.fetchone():
        p_hash, salt = hash_password("Staff@123")
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, salt, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("Civic Staff Officer", staff_email, p_hash, salt, "staff", now_str)
        )

    citizen_email = "citizen@demo.test"
    cursor.execute("SELECT id FROM users WHERE email = ?", (citizen_email,))
    citizen_row = cursor.fetchone()
    if not citizen_row:
        p_hash, salt = hash_password("Citizen@123")
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, salt, role, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("Ramesh Kumar (Citizen)", citizen_email, p_hash, salt, "citizen", now_str)
        )
        citizen_user_id = cursor.lastrowid
    else:
        citizen_user_id = citizen_row["id"]

    # 2. Seed services if table is empty
    cursor.execute("SELECT COUNT(*) as cnt FROM services")
    if cursor.fetchone()["cnt"] == 0:
        services_file = DATA_DIR / "services.json"
        if services_file.exists():
            with open(services_file, "r", encoding="utf-8") as f:
                services_list = json.load(f)
            for s in services_list:
                cursor.execute("""
                INSERT INTO services (
                    id, slug, category, department, name_en, name_hi, name_te,
                    desc_en, desc_hi, desc_te, eligibility, documents_json, steps_json,
                    fees, processing_time, source_name, source_url, last_reviewed, is_sample
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    s.get("id"),
                    s["slug"],
                    s["category"],
                    s["department"],
                    s["name_en"],
                    s["name_hi"],
                    s["name_te"],
                    s["desc_en"],
                    s["desc_hi"],
                    s["desc_te"],
                    s["eligibility"],
                    json.dumps(s["documents_json"], ensure_ascii=False),
                    json.dumps(s["steps_json"], ensure_ascii=False),
                    s["fees"],
                    s["processing_time"],
                    s["source_name"],
                    s["source_url"],
                    s["last_reviewed"],
                    s.get("is_sample", 1)
                ))

    # 3. Seed faqs if table is empty
    cursor.execute("SELECT COUNT(*) as cnt FROM faqs")
    if cursor.fetchone()["cnt"] == 0:
        faqs_file = DATA_DIR / "faqs.json"
        if faqs_file.exists():
            with open(faqs_file, "r", encoding="utf-8") as f:
                faqs_list = json.load(f)
            for item in faqs_list:
                cursor.execute("""
                INSERT INTO faqs (
                    id, category, question_en, question_hi, question_te,
                    answer_en, answer_hi, answer_te, source_name, source_url, last_reviewed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.get("id"),
                    item["category"],
                    item["question_en"],
                    item["question_hi"],
                    item["question_te"],
                    item["answer_en"],
                    item["answer_hi"],
                    item["answer_te"],
                    item["source_name"],
                    item["source_url"],
                    item["last_reviewed"]
                ))

    # 4. Seed 12+ sample grievances in varied statuses
    cursor.execute("SELECT COUNT(*) as cnt FROM grievances")
    if cursor.fetchone()["cnt"] == 0:
        sample_grievances = [
            {
                "reference": "GRV-2026-000101",
                "user_id": citizen_user_id,
                "name": "Ramesh Kumar",
                "contact": "citizen@demo.test",
                "subject": "Drinking water pipeline leakage at Ward 12 Main Road",
                "description": "Continuous freshwater leakage from underground joint near Community Hall Ward 12 for the past 48 hours causing road flooding.",
                "category": "Water Supply",
                "area": "Ward 12 - Gandhinagar",
                "landmark": "Near Community Hall, 3rd Cross",
                "attachment_path": None,
                "status": "In Progress",
                "priority": "High",
                "days_ago": 3,
                "history": [
                    {"status": "Submitted", "note": "Grievance received via web portal", "by": "System", "hours_after": 0},
                    {"status": "Under Review", "note": "Assigned to Water Supply Sub-Division 4", "by": "Staff Officer", "hours_after": 4},
                    {"status": "In Progress", "note": "Excavation and pipe collar clamp repair team dispatched", "by": "Junior Engineer", "hours_after": 20}
                ]
            },
            {
                "reference": "GRV-2026-000102",
                "user_id": citizen_user_id,
                "name": "Ramesh Kumar",
                "contact": "citizen@demo.test",
                "subject": "Streetlights not working on 5th Cross Residential Lane",
                "description": "Four streetlights in row have remained unlit for 5 nights. High risk of accidents and petty thefts in dark lane.",
                "category": "Municipal",
                "area": "Ward 07 - Subhash Nagar",
                "landmark": "Opposite Primary Health Clinic",
                "attachment_path": None,
                "status": "Resolved",
                "priority": "Medium",
                "days_ago": 6,
                "history": [
                    {"status": "Submitted", "note": "Grievance logged by citizen", "by": "System", "hours_after": 0},
                    {"status": "Under Review", "note": "Forwarded to electrical ward inspector", "by": "Staff Officer", "hours_after": 5},
                    {"status": "In Progress", "note": "Lineman assigned with replacement LED fixtures", "by": "Electrical JE", "hours_after": 18},
                    {"status": "Resolved", "note": "Choked driver replaced and 4 LED fittings tested operational", "by": "Electrical JE", "hours_after": 30}
                ]
            },
            {
                "reference": "GRV-2026-000103",
                "user_id": None,
                "name": "Sunita Devi",
                "contact": "9876543210",
                "subject": "Overflowing garbage bin and open dumping behind vegetable market",
                "description": "Municipal waste collection truck has not emptied the community bin for three consecutive days. Severe foul smell and stray animal menace.",
                "category": "Municipal",
                "area": "Ward 03 - Market Yard",
                "landmark": "North gate of Rythu Bazar",
                "attachment_path": None,
                "status": "Under Review",
                "priority": "High",
                "days_ago": 2,
                "history": [
                    {"status": "Submitted", "note": "Anonymous submission via civic portal", "by": "System", "hours_after": 0},
                    {"status": "Under Review", "note": "Sanitary inspector alerted for immediate tipper truck dispatch", "by": "Health Supervisor", "hours_after": 6}
                ]
            },
            {
                "reference": "GRV-2026-000104",
                "user_id": None,
                "name": "Anand Mohan",
                "contact": "anand.m@sample.mail",
                "subject": "Delay in processing Senior Citizen Pension application",
                "description": "Submitted application form along with age proof 50 days ago. Application number SCT-8839 still pending without status update.",
                "category": "Social Welfare & Pensions",
                "area": "Ward 15 - Shanti Nagar",
                "landmark": "Behind Mandal Revenue Office",
                "attachment_path": None,
                "status": "Under Review",
                "priority": "Medium",
                "days_ago": 5,
                "history": [
                    {"status": "Submitted", "note": "Grievance submitted online", "by": "System", "hours_after": 0},
                    {"status": "Under Review", "note": "File retrieved from Social Security desk for verification", "by": "Welfare Inspector", "hours_after": 24}
                ]
            },
            {
                "reference": "GRV-2026-000105",
                "user_id": None,
                "name": "Kavitha Reddy",
                "contact": "kavitha.reddy@example.com",
                "subject": "Frequent voltage fluctuation and power tripping during afternoon",
                "description": "Extreme high voltage swings (over 280V) damaging household refrigerator compressors and inverter batteries in sector 4.",
                "category": "Electricity",
                "area": "Ward 09 - Ashok Nagar",
                "landmark": "Transformer No. 4B, Sector 4",
                "attachment_path": None,
                "status": "Submitted",
                "priority": "High",
                "days_ago": 1,
                "history": [
                    {"status": "Submitted", "note": "Complaint registered through online grievance system", "by": "System", "hours_after": 0}
                ]
            },
            {
                "reference": "GRV-2026-000106",
                "user_id": None,
                "name": "P. Venkat",
                "contact": "9440112233",
                "subject": "Illegal private commercial billboard blocking road visibility at junction",
                "description": "An oversized hoarding frame erected on the curve of 80ft road blocking blind spot for vehicles turning left onto highway.",
                "category": "Municipal",
                "area": "Ward 18 - Ring Road",
                "landmark": "Junction near Petrol Bunk",
                "attachment_path": None,
                "status": "In Progress",
                "priority": "Medium",
                "days_ago": 4,
                "history": [
                    {"status": "Submitted", "note": "Public safety alert submitted", "by": "System", "hours_after": 0},
                    {"status": "Under Review", "note": "Town planning squad inspected hoarding legality", "by": "Town Planning Officer", "hours_after": 8},
                    {"status": "In Progress", "note": "Encroachment notice served; crane ordered for removal", "by": "Enforcement Wing", "hours_after": 32}
                ]
            },
            {
                "reference": "GRV-2026-000107",
                "user_id": citizen_user_id,
                "name": "Ramesh Kumar",
                "contact": "citizen@demo.test",
                "subject": "Erroneous commercial tariff applied on residential domestic power meter",
                "description": "Electricity bill for meter account #440219 charged at LT-2 commercial rates instead of LT-1 residential slab for October.",
                "category": "Electricity",
                "area": "Ward 12 - Gandhinagar",
                "landmark": "Near Community Hall",
                "attachment_path": None,
                "status": "Resolved",
                "priority": "Medium",
                "days_ago": 12,
                "history": [
                    {"status": "Submitted", "note": "Billing grievance filed with supporting domestic occupancy proof", "by": "System", "hours_after": 0},
                    {"status": "Under Review", "note": "Revenue section verified meter categorization records", "by": "Accounts Officer", "hours_after": 12},
                    {"status": "In Progress", "note": "Recalculation under Category 1 approved by Divisional Engineer", "by": "Divisional Engineer", "hours_after": 48},
                    {"status": "Resolved", "note": "Tariff category corrected to Domestic LT-1; credit adjustment applied to upcoming bill", "by": "Accounts Officer", "hours_after": 72}
                ]
            },
            {
                "reference": "GRV-2026-000108",
                "user_id": None,
                "name": "Mohammed Tariq",
                "contact": "tariq.m@sample.mail",
                "subject": "Request for compensation regarding private civil property boundary dispute",
                "description": "Neighbor built a compound wall allegedly 2 inches inside private boundary line. Demanding government compensation for lost land.",
                "category": "Revenue & Land",
                "area": "Ward 05 - Old City",
                "landmark": "Lane 4 near Clock Tower",
                "attachment_path": None,
                "status": "Rejected",
                "priority": "Low",
                "days_ago": 8,
                "history": [
                    {"status": "Submitted", "note": "Grievance received", "by": "System", "hours_after": 0},
                    {"status": "Under Review", "note": "Examined by revenue administration team", "by": "Tahsildar Office", "hours_after": 14},
                    {"status": "Rejected", "note": "Rejected: Private boundary disputes between titleholders are civil matters under jurisdiction of the competent Civil Court, not administrative civic grievance.", "by": "Tahsildar", "hours_after": 40}
                ]
            },
            {
                "reference": "GRV-2026-000109",
                "user_id": None,
                "name": "B. Lakshmi",
                "contact": "9988776655",
                "subject": "Sewage backflow in residential drain due to blocked main line",
                "description": "Heavy rainwater caused backpressure in municipal drainage. Manhole bubbling up foul dirty water into residential compound.",
                "category": "Water Supply",
                "area": "Ward 02 - Rajendra Nagar",
                "landmark": "House 14B, Behind Water Tank",
                "attachment_path": None,
                "status": "In Progress",
                "priority": "High",
                "days_ago": 2,
                "history": [
                    {"status": "Submitted", "note": "Drainage overflow alert logged", "by": "System", "hours_after": 0},
                    {"status": "Under Review", "note": "Assigned to emergency jetting squad", "by": "Control Room", "hours_after": 2},
                    {"status": "In Progress", "note": "High velocity vacuum jetting tanker at site clearing blockage", "by": "Sanitary Engineer", "hours_after": 10}
                ]
            },
            {
                "reference": "GRV-2026-000110",
                "user_id": None,
                "name": "Deepak Verma",
                "contact": "verma.d@sample.org",
                "subject": "Missing public bus stop shelter and vandalized passenger timetable",
                "description": "The commuter waiting shelter on Main Ring Road was dismantled during road widening but not re-installed. Commuters standing in rain.",
                "category": "Transport",
                "area": "Ward 18 - Ring Road",
                "landmark": "Bus Stop #24 near Tech Park Gate",
                "attachment_path": None,
                "status": "Under Review",
                "priority": "Low",
                "days_ago": 7,
                "history": [
                    {"status": "Submitted", "note": "Public transit amenities feedback submitted", "by": "System", "hours_after": 0},
                    {"status": "Under Review", "note": "Referred to City Transport Infrastructure cell for inclusion in upcoming quarterly bus shelter works", "by": "RTC Liaison", "hours_after": 36}
                ]
            },
            {
                "reference": "GRV-2026-000111",
                "user_id": None,
                "name": "Meera Bai",
                "contact": "meera.bai@example.net",
                "subject": "Ration dealer charging extra 50 rupees for free food grain distribution",
                "description": "Fair Price Shop #108 dealer forcibly demanding extra money for weighing bags under PMGKAY entitlement scheme.",
                "category": "Food & Civil Supplies",
                "area": "Ward 06 - Ambedkar Colony",
                "landmark": "Fair Price Shop 108",
                "attachment_path": None,
                "status": "In Progress",
                "priority": "High",
                "days_ago": 4,
                "history": [
                    {"status": "Submitted", "note": "Fair price malpractice complaint logged", "by": "System", "hours_after": 0},
                    {"status": "Under Review", "note": "Endorsed to District Civil Supplies Enforcement Squad", "by": "Civil Supplies Officer", "hours_after": 6},
                    {"status": "In Progress", "note": "Surprise audit initiated at FPS #108; stock records seized for inspection", "by": "Enforcement Inspector", "hours_after": 24}
                ]
            },
            {
                "reference": "GRV-2026-000112",
                "user_id": citizen_user_id,
                "name": "Ramesh Kumar",
                "contact": "citizen@demo.test",
                "subject": "Non-issuance of Infant Mother-Child Protection (MCP) card at Urban PHC",
                "description": "Visited Urban Primary Health Center twice for baby immunization card and pentavalent vaccine; staff turned us away citing staff shortage.",
                "category": "Health",
                "area": "Ward 07 - Subhash Nagar",
                "landmark": "Near Subhash Nagar Urban Health Center",
                "attachment_path": None,
                "status": "Resolved",
                "priority": "High",
                "days_ago": 9,
                "history": [
                    {"status": "Submitted", "note": "Health service delivery grievance submitted", "by": "System", "hours_after": 0},
                    {"status": "Under Review", "note": "District Medical & Health Officer notified", "by": "Medical Officer Desk", "hours_after": 4},
                    {"status": "In Progress", "note": "Medical Officer ordered dedicated auxiliary nurse midwife (ANM) desk", "by": "DMHO Liaison", "hours_after": 16},
                    {"status": "Resolved", "note": "Citizen contacted; MCP booklet issued and first dose vaccines administered successfully", "by": "Medical Officer", "hours_after": 36}
                ]
            },
            {
                "reference": "GRV-2026-000113",
                "user_id": None,
                "name": "Rajesh Gupta",
                "contact": "rgupta@sample.com",
                "subject": "Deep potholes on Ward 14 bypass road causing two-wheeler skids",
                "description": "After recent monsoon showers, road has 5 dangerous craters measuring over 1 foot deep near highway entry ramp.",
                "category": "Municipal",
                "area": "Ward 14 - Nehru Nagar",
                "landmark": "Highway Bypass Entry Ramp",
                "attachment_path": None,
                "status": "Submitted",
                "priority": "Medium",
                "days_ago": 1,
                "history": [
                    {"status": "Submitted", "note": "Road hazard alert submitted by citizen", "by": "System", "hours_after": 0}
                ]
            }
        ]

        now = datetime.now(timezone.utc)
        for g in sample_grievances:
            created_dt = now - timedelta(days=g["days_ago"])
            created_str = created_dt.isoformat()
            updated_str = created_str

            cursor.execute("""
            INSERT INTO grievances (
                reference, user_id, name, contact, subject, description,
                category, area, landmark, attachment_path, status, priority,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                g["reference"],
                g["user_id"],
                g["name"],
                g["contact"],
                g["subject"],
                g["description"],
                g["category"],
                g["area"],
                g["landmark"],
                g["attachment_path"],
                g["status"],
                g["priority"],
                created_str,
                updated_str
            ))
            g_id = cursor.lastrowid

            # insert history
            for h in g["history"]:
                h_dt = created_dt + timedelta(hours=h["hours_after"])
                h_str = h_dt.isoformat()
                cursor.execute("""
                INSERT INTO status_history (grievance_id, status, note, changed_by, changed_at)
                VALUES (?, ?, ?, ?, ?)
                """, (g_id, h["status"], h["note"], h["by"], h_str))
                updated_str = h_str

            # update updated_at to latest history timestamp
            cursor.execute("UPDATE grievances SET updated_at = ? WHERE id = ?", (updated_str, g_id))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    seed_data()
    print("Database initialized and seeded successfully.")
