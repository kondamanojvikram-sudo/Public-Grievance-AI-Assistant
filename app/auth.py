import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict
from starlette.requests import Request

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = "dev-insecure-secret-key-grievance-prototype-change-in-prod"
    print("WARNING: [SECURITY] SECRET_KEY not found in environment; using default dev fallback. Do not use in production!")

# In-memory sliding window rate limiter: (key) -> list of timestamps
_rate_limits = defaultdict(list)

def check_rate_limit(request: Request, prefix: str = "general", limit: int = 20, window_seconds: float = 60.0) -> bool:
    client_ip = request.client.host if request.client else "127.0.0.1"
    key = f"{prefix}:{client_ip}"
    now = time.time()

    # Prune old timestamps
    timestamps = [ts for ts in _rate_limits[key] if now - ts < window_seconds]
    if len(timestamps) >= limit:
        _rate_limits[key] = timestamps
        return False

    timestamps.append(now)
    _rate_limits[key] = timestamps
    return True

def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    salt_bytes = bytes.fromhex(salt)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 100_000)
    return key.hex(), salt

def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    new_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(new_hash, expected_hash)

def generate_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_hex(24)
        request.session["csrf_token"] = token
    return token

def validate_csrf_token(request: Request, submitted_token: str) -> bool:
    session_token = request.session.get("csrf_token")
    if not session_token or not submitted_token:
        return False
    return hmac.compare_digest(session_token, submitted_token)

def get_session_user(request: Request) -> dict | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return {
        "id": user_id,
        "name": request.session.get("user_name"),
        "email": request.session.get("user_email"),
        "role": request.session.get("user_role")
    }
