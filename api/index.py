import sys
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.main import app
from app.db import DB_PATH, init_db, seed_data
from app.retrieval import get_retriever

# Ensure DB is created on cold starts in serverless environment
try:
    if not DB_PATH.exists():
        init_db()
        seed_data()
        get_retriever()
except Exception:
    pass
