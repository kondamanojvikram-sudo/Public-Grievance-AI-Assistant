# Public Grievance AI Assistant (HACK-P438)

A full-stack citizen-facing prototype designed for public service discovery, information retrieval, and civic grievance submission with real-time status tracking and an administrative management queue.

> **Disclaimer**: This is a prototype populated with synthetic sample data modelled on Indian civic and public services. It is strictly a demonstration prototype and is **NOT** affiliated with or an official portal of any government department.

---

## 1. Quick Start

### Prerequisites
- Python 3.10+ (tested on Python 3.13 / 3.14 / 3.15)
- No Node.js, npm, or external build steps required.

### Installation
Clone or navigate to the project directory:
```bash
cd grievance-assistant
pip install -r requirements.txt
```

### Run Server
```bash
uvicorn app.main:app --reload
```
Open your web browser and navigate to:
**[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 2. Demo Credentials

The prototype comes pre-seeded with sample accounts and 13 initial civic grievances in varied workflow states:

| Role | Email | Password | Access / Purpose |
| :--- | :--- | :--- | :--- |
| **Staff Officer** | `staff@demo.test` | `Staff@123` | Access `/admin` staff queue, filter, review, update statuses, and log administrative notes |
| **Citizen** | `citizen@demo.test` | `Citizen@123` | Access `/dashboard`, view logged requests, check progress timelines |
| **Anonymous** | *(None)* | *(None)* | Citizens can file grievances and track them anonymously via `/track` without logging in |

---

## 3. Tech Stack & Architecture

- **Backend**: Python FastAPI, Uvicorn, SQLite3 via standard library (zero ORM, raw parameterized SQL queries with indices).
- **Authentication**: Starlette `SessionMiddleware` with cryptographically secure session cookies. Passwords hashed using PBKDF2 (`hashlib.pbkdf2_hmac` with 100,000 SHA-256 iterations and random 16-byte hex salts).
- **Frontend**: Server-rendered Jinja2 templates, vanilla JavaScript, and semantic HTML5 styled with vanilla CSS.
- **Search & Retrieval**: Pure-Python BM25 / TF-IDF engine over bilingual and trilingual curated knowledge base (Services + FAQs). Works 100% offline without any API keys or network calls.
  - *Optional*: If `GEMINI_API_KEY` is present in the environment, the app uses it strictly to politely rephrase retrieved context; the app operates completely and autonomously without it.
- **Security & Privacy**:
  - Parameterized queries on all SQLite statements.
  - In-memory sliding-window rate limiting (20 requests/minute per client IP) on chat and grievance submissions.
  - Cryptographic CSRF tokens on all POST forms.
  - Server-side file upload inspection (max 2 MB, strictly `.pdf`, `.jpg`, `.jpeg`, `.png`, stored under random UUID names).
  - Controlled file access route (`/uploads/{filename}`) restricted only to staff and the respective owner.
  - Data minimization: does not collect Aadhaar, PAN, bank accounts, or sensitive identifiers.

---

## 4. How the Retrieval Engine Works

The search engine (`app/retrieval.py`) is implemented in pure Python with zero external libraries:
1. **Document Corpus**: Aggregates all 22+ services and 26+ FAQs. Each document indexes English, Hindi, and Telugu terms, category names, departments, eligibility rules, and procedural steps.
2. **Multilingual Tokenizer**: Regex-based tokenization supporting Unicode alphanumeric scripts (Devanagari, Telugu, Latin) with English and question-stopword pruning (`app/retrieval.py`).
3. **BM25 Scoring**:
   $$\text{Score}(D, Q) = \sum_{q \in Q} \text{IDF}(q) \cdot \frac{f(q, D) \cdot (k_1 + 1)}{f(q, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avg\_doc\_len}}\right)}$$
   with $k_1 = 1.5$, $b = 0.75$, and standard BM25 IDF:
   $$\text{IDF}(q) = \ln\left(1 + \frac{N - n(q) + 0.5}{n(q) + 0.5}\right)$$
4. **Confidence Gating & Refusal**:
   - Computes both raw BM25 score and query keyword coverage ratio ($\frac{\text{matched query tokens}}{\text{total unique query tokens}}$).
   - If score $< 3.5$ or term coverage $< 45\%$: the model **refuses to guess**, returns `confidence: "low"`, no fabricated sources, and suggests filing a formal civic grievance or browsing the directory.
   - If score $\ge 7.0$ and coverage $\ge 60\%$: returns `confidence: "high"` with exact verified source links and last reviewed dates.

---

## 5. How to Add Services, FAQs, and Languages

### Adding a Service
Add a JSON object to `app/data/services.json` with the following structure:
```json
{
  "id": 23,
  "slug": "new-service-slug",
  "category": "Municipal",
  "department": "Department Name",
  "name_en": "Service Name in English",
  "name_hi": "सेवा का नाम हिंदी में",
  "name_te": "సేవ పేరు తెలుగులో",
  "desc_en": "Description...",
  "desc_hi": "विवरण...",
  "desc_te": "వివరణ...",
  "eligibility": "Eligibility criteria",
  "documents_json": ["Doc 1", "Doc 2"],
  "steps_json": ["Step 1", "Step 2"],
  "fees": "Fee structure",
  "processing_time": "Estimated turnaround",
  "source_name": "Portal Name",
  "source_url": "https://india.gov.in",
  "last_reviewed": "2026-10-01",
  "is_sample": 1
}
```
Delete `app/grievance.db` or run `init_db()` & `seed_data()` to reload into SQLite.

### Adding an FAQ
Add an entry to `app/data/faqs.json`:
```json
{
  "id": 27,
  "category": "Water Supply",
  "question_en": "What is the procedure for water testing?",
  "question_hi": "पानी की जांच की क्या प्रक्रिया है?",
  "question_te": "నీటి నాణ్యత పరీక్ష విధానం ఏమిటి?",
  "answer_en": "Citizens can submit a sample...",
  "answer_hi": "नागरिक नमूना जमा कर सकते हैं...",
  "answer_te": "పౌరులు నమూనాను సమర్పించవచ్చు...",
  "source_name": "Sample Municipal Water Portal",
  "source_url": "https://example.gov.in/sample/water-board",
  "last_reviewed": "2026-10-15"
}
```

### Adding a New Language (e.g., Tamil `ta`)
1. Add the translation dictionary under the new language code in `app/data/translations.json`.
2. Add language display name in `SUPPORTED_LANGUAGES` in `app/i18n.py`.
3. Add the `<option value="ta">தமிழ்</option>` tag in `app/templates/base.html`.

---

## 6. Engineering Decisions Made

1. **Progressive Enhancement**: The multi-step grievance filing form uses vanilla JavaScript to provide a 4-step wizard with review validation. However, if JavaScript is disabled in the browser, all form fields are rendered together in a semantic HTML layout, ensuring 100% accessible submittability.
2. **Zero-Dependency Architecture**: Built without Node.js or ORM bloat to allow instant setup, rapid testing, and predictable deployment on Windows, Linux, and macOS.
3. **Controlled File Attachments**: Citizen attachments are never exposed in a public `/static` directory; they are stored under unguessable UUID filenames in `app/uploads/` and served through a permission-checked route (`/uploads/{filename}`).
4. **Duplicate Grievance Warning**: When a submission matches an existing ticket in the same category and ward within recent days, the user receives an alert acknowledging the potential duplicate, but is still allowed to submit their grievance.

---

## 7. Known Limitations

- **In-Memory Rate Limiting**: The rate limiter uses an in-memory dictionary. If running with multiple horizontal Uvicorn worker processes (`--workers > 1`), an external cache like Redis would be required for shared sliding windows.
- **Audio Output**: The speech feature supports speech-to-text input using the browser's native Web Speech API (`SpeechRecognition`). It relies on browser support (e.g., Chrome/Edge/Safari) and does not synthesize text-to-speech audio responses.
- **Database Scalability**: Designed for hackathon prototypes with SQLite; for heavy enterprise concurrency with hundreds of concurrent staff writes, migration to PostgreSQL would be recommended.
