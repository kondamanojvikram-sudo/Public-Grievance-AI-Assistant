import json
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "translations.json"
_translations = {}

def load_translations():
    global _translations
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            _translations = json.load(f)
    else:
        _translations = {"en": {}, "hi": {}, "te": {}}

load_translations()

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "हिन्दी",
    "te": "తెలుగు"
}

def t(key: str, lang: str = "en") -> str:
    if not _translations:
        load_translations()
    if lang not in _translations:
        lang = "en"
    # check requested lang
    if key in _translations[lang]:
        return _translations[lang][key]
    # fallback to english
    if key in _translations.get("en", {}):
        return _translations["en"][key]
    # fallback to key
    return key

def get_lang_from_request(request) -> str:
    lang = request.cookies.get("lang", "en")
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"
    return lang
