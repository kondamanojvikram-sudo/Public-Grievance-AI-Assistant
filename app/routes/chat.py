from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from app.auth import check_rate_limit
from app.i18n import t, get_lang_from_request
from app.retrieval import answer_query

router = APIRouter()

class ChatRequest(BaseModel):
    message: str = Field(..., max_length=1000)
    language: str = Field("en", max_length=10)

@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    templates = request.app.state.templates
    lang = get_lang_from_request(request)

    suggested_questions = {
        "en": [
            "What documents do I need for a birth certificate?",
            "How can I report a broken or non-working street light in my area?",
            "What is the procedure for getting a new domestic water supply connection?",
            "How do I renew an expired driving licence?"
        ],
        "hi": [
            "जन्म प्रमाण पत्र के लिए मुझे किन दस्तावेजों की आवश्यकता है?",
            "मैं अपने क्षेत्र में खराब या बंद स्ट्रीट लाइट की रिपोर्ट कैसे कर सकता हूँ?",
            "नया घरेलू जल आपूर्ति कनेक्शन प्राप्त करने की क्या प्रक्रिया है?",
            "मैं समाप्त हो चुके ड्राइविंग लाइसेंस को कैसे नवीनीकृत करूँ?"
        ],
        "te": [
            "జనన ధృవీకరణ పత్రం కొరకు నాకు ఏ పత్రాలు అవసరం?",
            "నా ప్రాంతంలో పనిచేయని వీధి దీపం గురించి ఎలా ఫిర్యాదు చేయాలి?",
            "కొత్త గృహ తాగునీటి కనెక్షన్ పొందే విధానం ఏమిటి?",
            "గడువు ముగిసిన డ్రైవింగ్ లైసెన్స్‌ను ఎలా పునరుద్ధరించుకోవాలి?"
        ]
    }.get(lang, [])

    return templates.TemplateResponse(request=request, name="chat.html", context={
        "lang": lang,
        "suggested_questions": suggested_questions,
        "t": t
    })

@router.post("/api/chat")
async def chat_api(request: Request, body: ChatRequest):
    # Enforce in-memory rate limit: 20 req/min per IP
    if not check_rate_limit(request, prefix="chat", limit=20, window_seconds=60.0):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a minute before sending more queries."
        )

    lang = body.language or get_lang_from_request(request)
    if lang not in ["en", "hi", "te"]:
        lang = "en"

    result = answer_query(body.message, language=lang)
    return JSONResponse(content=result)
