import math
import os
import re
import json
from collections import Counter
from app.db import get_db_connection
from app.i18n import t

# BM25 Hyperparameters
K1 = 1.5
B = 0.75
CONFIDENCE_HIGH_THRESHOLD = 7.0
CONFIDENCE_MED_THRESHOLD = 3.5

STOPWORDS = {
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours',
    'he', 'him', 'his', 'himself', 'she', 'her', 'hers', 'itself', 'they', 'them', 'their',
    'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is', 'are', 'was',
    'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing',
    'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until', 'while', 'of', 'at',
    'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through', 'during', 'before',
    'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over',
    'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where', 'why', 'how',
    'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor',
    'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's', 't', 'can', 'will', 'just',
    'don', 'should', 'now', 'need', 'want', 'tell', 'give', 'know', 'please'
}

def tokenize(text: str, remove_stopwords: bool = True) -> list[str]:
    if not text:
        return []
    words = re.findall(r"[\w]+", text.lower())
    filtered = []
    for w in words:
        if len(w) <= 1:
            continue
        if remove_stopwords and w in STOPWORDS:
            continue
        filtered.append(w)
    return filtered

class KnowledgeBaseRetriever:
    def __init__(self):
        self.documents = []
        self.doc_tokens = []
        self.doc_lens = []
        self.avg_doc_len = 0.0
        self.doc_count = 0
        self.df = Counter()
        self.idf = {}
        self.load_index()

    def load_index(self):
        conn = get_db_connection()
        cursor = conn.cursor()

        docs = []

        # Load services
        cursor.execute("SELECT * FROM services")
        for row in cursor.fetchall():
            s = dict(row)
            try:
                docs_list = json.loads(s.get("documents_json", "[]"))
            except Exception:
                docs_list = []
            try:
                steps_list = json.loads(s.get("steps_json", "[]"))
            except Exception:
                steps_list = []

            searchable_text = f"{s['name_en']} {s['name_hi']} {s['name_te']} {s['category']} {s['department']} {s['desc_en']} {s['desc_hi']} {s['desc_te']} {s['eligibility']} {' '.join(docs_list)} {' '.join(steps_list)} {s['fees']} {s['processing_time']}"

            docs.append({
                "type": "service",
                "id": s["id"],
                "slug": s["slug"],
                "category": s["category"],
                "department": s["department"],
                "name_en": s["name_en"],
                "name_hi": s["name_hi"],
                "name_te": s["name_te"],
                "desc_en": s["desc_en"],
                "desc_hi": s["desc_hi"],
                "desc_te": s["desc_te"],
                "eligibility": s["eligibility"],
                "documents": docs_list,
                "steps": steps_list,
                "fees": s["fees"],
                "processing_time": s["processing_time"],
                "source_name": s["source_name"],
                "source_url": s["source_url"],
                "last_reviewed": s["last_reviewed"],
                "searchable_text": searchable_text
            })

        # Load FAQs
        cursor.execute("SELECT * FROM faqs")
        for row in cursor.fetchall():
            f = dict(row)
            searchable_text = f"{f['category']} {f['question_en']} {f['question_hi']} {f['question_te']} {f['answer_en']} {f['answer_hi']} {f['answer_te']}"
            docs.append({
                "type": "faq",
                "id": f["id"],
                "category": f["category"],
                "question_en": f["question_en"],
                "question_hi": f["question_hi"],
                "question_te": f["question_te"],
                "answer_en": f["answer_en"],
                "answer_hi": f["answer_hi"],
                "answer_te": f["answer_te"],
                "source_name": f["source_name"],
                "source_url": f["source_url"],
                "last_reviewed": f["last_reviewed"],
                "searchable_text": searchable_text
            })

        conn.close()

        self.documents = docs
        self.doc_count = len(docs)
        self.doc_tokens = [tokenize(d["searchable_text"], remove_stopwords=True) for d in docs]
        self.doc_lens = [len(toks) for toks in self.doc_tokens]
        self.avg_doc_len = sum(self.doc_lens) / max(1, self.doc_count)

        df = Counter()
        for tokens in self.doc_tokens:
            for t in set(tokens):
                df[t] += 1
        self.df = df

        idf = {}
        for term, freq in df.items():
            idf[term] = math.log(1.0 + (self.doc_count - freq + 0.5) / (freq + 0.5))
        self.idf = idf

    def score_query(self, query: str) -> list[tuple[float, float, dict]]:
        query_tokens = tokenize(query, remove_stopwords=True)
        if not query_tokens:
            query_tokens = tokenize(query, remove_stopwords=False)
        if not query_tokens:
            return []

        unique_q_terms = set(query_tokens)
        scores = []

        for idx, doc in enumerate(self.documents):
            doc_toks = self.doc_tokens[idx]
            doc_len = self.doc_lens[idx]
            tok_counts = Counter(doc_toks)

            score = 0.0
            matched_terms = 0
            for qt in query_tokens:
                if qt in tok_counts:
                    freq = tok_counts[qt]
                    term_idf = self.idf.get(qt, 1.0)
                    numerator = freq * (K1 + 1.0)
                    denominator = freq + K1 * (1.0 - B + B * (doc_len / max(1.0, self.avg_doc_len)))
                    score += term_idf * (numerator / denominator)

            for uqt in unique_q_terms:
                if uqt in tok_counts:
                    matched_terms += 1

            term_coverage = matched_terms / len(unique_q_terms) if unique_q_terms else 0.0

            # Boost FAQ if question terms match
            if doc["type"] == "faq":
                q_text = f"{doc['question_en']} {doc['question_hi']} {doc['question_te']}".lower()
                for qt in unique_q_terms:
                    if qt in q_text:
                        score += 2.5

            if term_coverage >= 0.75:
                score *= 1.3
            elif term_coverage < 0.4:
                score *= 0.2

            if score > 0:
                scores.append((score, term_coverage, doc))

        scores.sort(key=lambda x: x[0], reverse=True)
        return scores

_retriever = None

def get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = KnowledgeBaseRetriever()
    return _retriever

GREETINGS = {
    "hi", "hello", "hey", "namaste", "namaskar", "namaskaram",
    "good morning", "good evening", "good afternoon", "help"
}

def is_greeting(text: str) -> bool:
    clean = re.sub(r"[^\w\s]", "", text.strip().lower())
    return clean in GREETINGS or clean.startswith("hello") or clean.startswith("hi ") or clean.startswith("namaste")

def answer_query(user_message: str, language: str = "en") -> dict:
    truncated = user_message.strip()[:500]

    if not truncated:
        msg = {
            "en": "Please type a question regarding public services, documents, eligibility, or civic grievances.",
            "hi": "कृपया सार्वजनिक सेवाओं, दस्तावेजों, पात्रता या नागरिक शिकायतों के संबंध में कोई प्रश्न पूछें।",
            "te": "దయచేసి ప్రజా సేవలు, పత్రాలు, అర్హతలు లేదా పౌర సమస్యలకు సంబంధించిన ప్రశ్నను టైప్ చేయండి."
        }.get(language, "Please type a question regarding public services.")
        return {
            "answer": msg,
            "confidence": "low",
            "sources": [],
            "suggested_action": {"label": t("btn_explore_services", language), "url": "/services"}
        }

    if is_greeting(truncated):
        msg = {
            "en": "Hello! I am your Public Grievance AI Assistant. I can help you find information on 20+ public civic services (birth/death certificates, water, electricity, pensions, transport, ration, health, education), or guide you in submitting a civic grievance.",
            "hi": "नमस्ते! मैं आपका सार्वजनिक शिकायत एआई सहायक हूँ। मैं 20+ नागरिक सेवाओं (जन्म/मृत्यु प्रमाण पत्र, जल, बिजली, पेंशन, परिवहन, राशन, स्वास्थ्य, शिक्षा) की जानकारी दे सकता हूँ या शिकायत दर्ज करने में सहायता कर सकता हूँ।",
            "te": "నమస్కారం! నేను మీ ప్రజా సమస్యల పరిష్కార ఏఐ సహాయకుడిని. 20+ ప్రభుత్వ ప్రజా సేవలు (జనన/మరణ ధృవీకరణ పత్రాలు, నీరు, విద్యుత్, పెన్షన్లు, రవాణా, రేషన్, ఆరోగ్యం, విద్య) సమాచారం లేదా సమస్య నమోదు కొరకు నేను సహాయం చేయగలను."
        }.get(language, "Hello! How can I assist you with public services today?")
        return {
            "answer": msg,
            "confidence": "high",
            "sources": [],
            "suggested_action": {"label": t("btn_explore_services", language), "url": "/services"}
        }

    retriever = get_retriever()
    scored_results = retriever.score_query(truncated)

    if not scored_results:
        return _fallback_refusal(language)

    top_score, top_coverage, top_doc = scored_results[0]

    if top_score < CONFIDENCE_MED_THRESHOLD or top_coverage < 0.45:
        return _fallback_refusal(language)

    confidence = "high" if (top_score >= CONFIDENCE_HIGH_THRESHOLD and top_coverage >= 0.6) else "medium"

    answer_text = ""
    sources = []
    suggested_action = None

    if top_doc["type"] == "faq":
        if language == "hi":
            answer_text = top_doc.get("answer_hi") or top_doc["answer_en"]
            doc_title = top_doc.get("question_hi") or top_doc["question_en"]
        elif language == "te":
            answer_text = top_doc.get("answer_te") or top_doc["answer_en"]
            doc_title = top_doc.get("question_te") or top_doc["question_en"]
        else:
            answer_text = top_doc["answer_en"]
            doc_title = top_doc["question_en"]

        sources.append({
            "title": f"FAQ: {doc_title}",
            "url": top_doc["source_url"],
            "source_name": top_doc["source_name"],
            "last_reviewed": top_doc["last_reviewed"]
        })
        suggested_action = {
            "label": t("btn_file_grievance", language),
            "url": "/grievance/new"
        }

    else:  # service
        if language == "hi":
            name = top_doc["name_hi"]
            desc = top_doc["desc_hi"]
            elib_label = "पात्रता"
            docs_label = "आवश्यक दस्तावेज"
            steps_label = "प्रक्रिया के चरण"
            fee_label = "शुल्क"
            time_label = "समय"
        elif language == "te":
            name = top_doc["name_te"]
            desc = top_doc["desc_te"]
            elib_label = "అర్హత"
            docs_label = "అవసరమైన పత్రాలు"
            steps_label = "దరఖాస్తు విధానం"
            fee_label = "రుసుము"
            time_label = "పట్టే సమయం"
        else:
            name = top_doc["name_en"]
            desc = top_doc["desc_en"]
            elib_label = "Eligibility"
            docs_label = "Required Documents"
            steps_label = "Steps"
            fee_label = "Fees"
            time_label = "Processing Time"

        docs_summary = ", ".join(top_doc["documents"][:4])
        steps_summary = "; ".join(top_doc["steps"][:3])

        answer_text = f"{name}: {desc}\n\n• {elib_label}: {top_doc['eligibility']}\n• {docs_label}: {docs_summary}\n• {steps_label}: {steps_summary}\n• {fee_label}: {top_doc['fees']}\n• {time_label}: {top_doc['processing_time']}."

        sources.append({
            "title": f"Service Guide: {name}",
            "url": top_doc["source_url"],
            "source_name": top_doc["source_name"],
            "last_reviewed": top_doc["last_reviewed"]
        })
        suggested_action = {
            "label": f"{t('view_details', language)}: {name}",
            "url": f"/services/{top_doc['slug']}"
        }

    answer_text = _optional_gemini_rephrase(answer_text, truncated, language)

    return {
        "answer": answer_text,
        "confidence": confidence,
        "sources": sources,
        "suggested_action": suggested_action
    }

def _fallback_refusal(language: str) -> dict:
    no_answer_msg = {
        "en": "I cannot answer this question from the curated civic knowledge base. I can only provide guidance on supported public services and procedures. Please explore the Services Directory or submit a formal civic grievance.",
        "hi": "मैं ज्ञानकोष से इस प्रश्न का उत्तर देने में असमर्थ हूँ। मैं केवल समर्थित सार्वजनिक सेवाओं और प्रक्रियाओं पर मार्गदर्शन प्रदान कर सकता हूँ। कृपया सेवा निर्देशिका देखें या एक नई नागरिक शिकायत दर्ज करें।",
        "te": "నా వద్ద ఉన్న పౌర సమాచార డేటా ఆధారంగా దీనికి సమాధానం ఇవ్వలేకపోతున్నాను. నేను అధికారికంగా చేర్చబడిన సేవలపై మాత్రమే మార్గదర్శనం ఇవ్వగలను. దయచేసి సేవల డైరెక్టరీని పరిశీలించండి లేదా సమస్య నమోదు చేయండి."
    }.get(language, "I cannot answer this question from the curated civic knowledge base.")

    return {
        "answer": no_answer_msg,
        "confidence": "low",
        "sources": [],
        "suggested_action": {
            "label": t("btn_file_grievance", language),
            "url": "/grievance/new"
        }
    }

def _optional_gemini_rephrase(base_answer: str, user_query: str, language: str) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return base_answer

    import urllib.request
    import urllib.error

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        prompt = (
            f"You are a helpful civic assistant. Using ONLY the facts in the following retrieved context, "
            f"politely rephrase the answer in language '{language}' to answer the citizen's query. "
            f"Do not invent facts, laws, or deep links.\n\n"
            f"Context:\n{base_answer}\n\n"
            f"Citizen Query: {user_query}\n"
        )
        payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=4) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            candidate = res_data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
            if candidate and candidate.strip():
                return candidate.strip()
    except Exception:
        pass

    return base_answer
