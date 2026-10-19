
import os
import re
import logging
import requests

from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ==========================================
# 1. FLASK APPLICATION CONFIGURATION
# ==========================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "development-key-change-before-production"
)

app.logger.setLevel(logging.INFO)


# ==========================================
# 2. DATABASE CONFIGURATION
# ==========================================

database_url = os.environ.get(
    "DATABASE_URL", "sqlite:///college_chatbot.db"
)

if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://", "postgresql://", 1
    )

if (
    database_url.startswith("postgresql://")
    and "+psycopg" not in database_url
):
    database_url = database_url.replace(
        "postgresql://", "postgresql+psycopg://", 1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ==========================================
# 3. DATABASE MODELS
# ==========================================

class FAQ(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), default="General")
    keywords = db.Column(db.Text, default="")


class ChatLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_question = db.Column(db.Text, nullable=False)
    bot_answer = db.Column(db.Text, nullable=False)
    matched_faq_id = db.Column(db.Integer, nullable=True)
    confidence = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )


# ==========================================
# 4. LOAD FAQ DATA
# ==========================================

def load_faq_data():
    import json
    from pathlib import Path

    data_path = Path(__file__).parent / "faq_data.json"

    with data_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def seed_database():
    if FAQ.query.count() == 0:
        items = load_faq_data()

        for item in items:
            db.session.add(
                FAQ(
                    question=item["question"],
                    answer=item["answer"],
                    category=item.get("category", "General"),
                    keywords=", ".join(
                        item.get("keywords", [])
                    )
                )
            )

        db.session.commit()


# ==========================================
# 5. FAQ SEARCH
# ==========================================

def normalise(text):
    return re.sub(
        r"\s+", " ", (text or "").strip().lower()
    )


def build_search_text(faq):
    return " ".join([
        faq.question or "",
        faq.category or "",
        faq.keywords or ""
    ])


def find_best_answer(user_question):
    faqs = FAQ.query.all()

    if not faqs:
        return None, 0.0

    documents = [
        build_search_text(faq) for faq in faqs
    ]

    vectorizer = TfidfVectorizer(
        lowercase=True,
        analyzer="word",
        ngram_range=(1, 2),
        sublinear_tf=True,
        strip_accents="unicode"
    )

    try:
        matrix = vectorizer.fit_transform(
            documents + [normalise(user_question)]
        )

        scores = cosine_similarity(
            matrix[-1], matrix[:-1]
        ).flatten()

    except ValueError:
        return None, 0.0

    best_index = int(scores.argmax())
    confidence = float(scores[best_index])

    threshold = float(
        os.environ.get("MATCH_THRESHOLD", "0.16")
    )

    if confidence < threshold:
        return None, confidence

    return faqs[best_index], confidence


# ==========================================
# 6. GEMINI AI INTEGRATION
# ==========================================

def get_gemini_answer(user_question):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not api_key:
        app.logger.error(
            "GEMINI_API_KEY is missing from the running environment."
        )
        return None

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/gemini-2.5-flash:generateContent"
    )

    prompt = (
        "You are a helpful college enquiry assistant for "
        "SRIT (Srinivasa Ramanujan Institute of Technology), "
        "Anantapur, Andhra Pradesh, India. "
        "Answer politely and clearly. "
        "Do not invent official college facts, fees, admission "
        "rules, dates, or contact details. "
        "If you do not know a verified answer, tell the student "
        "to confirm it with the college office.\n\n"
        f"Student question: {user_question}"
    )

    try:
        response = requests.post(
            url,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json"
            },
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 300
                }
            },
            timeout=25
        )

        if response.status_code != 200:
            # Log the error without exposing the API key.
            app.logger.error(
                "Gemini API returned HTTP %s: %s",
                response.status_code,
                response.text[:1000]
            )
            return None

        data = response.json()

        candidates = data.get("candidates", [])

        if not candidates:
            app.logger.warning(
                "Gemini returned no answer candidates."
            )
            return None

        parts = candidates[0].get(
            "content", {}
        ).get("parts", [])

        answer = " ".join(
            part["text"]
            for part in parts
            if isinstance(part.get("text"), str)
        ).strip()

        if not answer:
            app.logger.warning(
                "Gemini returned an empty answer."
            )
            return None

        return answer

    except requests.RequestException:
        app.logger.exception(
            "Could not connect to the Gemini API."
        )
        return None

    except (ValueError, KeyError, TypeError, IndexError):
        app.logger.exception(
            "Could not process the Gemini response."
        )
        return None


# ==========================================
# 7. HOME PAGE
# ==========================================

@app.get("/")
def home():
    return render_template("index.html")


# ==========================================
# 8. HEALTH CHECK
# ==========================================

@app.get("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "AI College Enquiry Chatbot"
    })


# ==========================================
# 9. GEMINI CONFIGURATION DIAGNOSTIC
# ==========================================

@app.get("/api/check-gemini-config")
def check_gemini_config():
    api_key = os.environ.get("GEMINI_API_KEY", "")

    return jsonify({
        "gemini_key_configured": bool(api_key.strip())
    })


# ==========================================
# 10. SUGGESTED QUESTIONS
# ==========================================

@app.get("/api/suggestions")
def suggestions():
    faqs = FAQ.query.order_by(
        FAQ.id.asc()
    ).limit(6).all()

    return jsonify([
        {
            "question": faq.question,
            "category": faq.category
        }
        for faq in faqs
    ])


# ==========================================
# 11. MAIN CHATBOT
# ==========================================

@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}

    question = payload.get("message", "")

    if not isinstance(question, str):
        return jsonify({
            "error": "Please enter a valid text question."
        }), 400

    question = question.strip()

    if not question:
        return jsonify({
            "error": "Please type a question first."
        }), 400

    if len(question) > 1000:
        return jsonify({
            "error": "Please keep your question under 1,000 characters."
        }), 400

    # First, search the FAQ database.
    faq, confidence = find_best_answer(question)

    if faq is not None:
        answer = faq.answer
        faq_id = faq.id
        category = faq.category or "General"

    else:
        # If there is no matching FAQ, ask Gemini.
        answer = get_gemini_answer(question)
        faq_id = None

        if answer is not None:
            category = "AI Generated"
        else:
            answer = (
                "Sorry, I couldn't find an answer right now. "
                "Please try again later or contact the "
                "college office for confirmation."
            )
            category = "Not found"

    # Save the conversation to the database.
    try:
        db.session.add(
            ChatLog(
                user_question=question,
                bot_answer=answer,
                matched_faq_id=faq_id,
                confidence=round(confidence, 4)
            )
        )

        db.session.commit()

    except Exception:
        db.session.rollback()
        app.logger.exception(
            "Could not save chat history."
        )

    return jsonify({
        "answer": answer,
        "category": category,
        "confidence": round(confidence, 3),
        "matched": faq is not None
    })


# ==========================================
# 12. INITIALIZE DATABASE
# ==========================================

with app.app_context():
    db.create_all()
    seed_database()


@app.route("/api/check-gemini-config")
def check_gemini_config():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    return {
        "gemini_key_configured": bool(api_key)
    }

# ==========================================
# 13. START APPLICATION
# ==========================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=False
    )
