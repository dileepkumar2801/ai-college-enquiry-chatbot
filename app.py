
import os
import re
import requests
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "change-this-before-public-deployment"
)

# Database configuration
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


# FAQ database model
class FAQ(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), default="General")
    keywords = db.Column(db.Text, default="")


# Chat history model
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


# Load FAQ data from JSON
def load_faq_data():
    import json
    from pathlib import Path

    data_path = Path(__file__).parent / "faq_data.json"

    with data_path.open("r", encoding="utf-8") as file:
        return json.load(file)


# Add initial FAQs if the database is empty
def seed_database():
    if FAQ.query.count() == 0:
        for item in load_faq_data():
            db.session.add(
                FAQ(
                    question=item["question"],
                    answer=item["answer"],
                    category=item.get("category", "General"),
                    keywords=", ".join(item.get("keywords", []))
                )
            )

        db.session.commit()


# Normalize text
def normalise(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


# Prepare FAQ search text
def build_search_text(faq):
    return " ".join([
        faq.question,
        faq.category or "",
        faq.keywords or ""
    ])


# Find the closest FAQ answer
def find_best_answer(user_question):
    faqs = FAQ.query.all()

    if not faqs:
        return None, 0.0

    documents = [
        build_search_text(faq)
        for faq in faqs
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


# Gemini AI integration
def get_gemini_answer(user_question):
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        app.logger.warning("GEMINI_API_KEY is not configured.")
        return None

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/gemini-2.5-flash:generateContent"
    )

    prompt = (
        "You are a helpful college enquiry assistant for "
        "SRIT (Srinivasa Ramanujan Institute of Technology), "
        "Anantapur, Andhra Pradesh, India. Answer politely "
        "and clearly. Do not invent official college facts, "
        "fees, admission rules, dates, or contact details. "
        "If you do not know a verified answer, say that the "
        "student should confirm it with the college office.\n\n"
        f"Student question: {user_question}"
    )

    try:
        response = requests.post(
            url,
            headers={"x-goog-api-key": api_key},
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
            timeout=20
        )

        if response.status_code != 200:
            app.logger.warning(
                "Gemini API returned status %s",
                response.status_code
            )
            return None

        data = response.json()

        return (
            data["candidates"][0]["content"]["parts"][0]["text"]
            .strip()
        )

    except (
        requests.RequestException,
        KeyError,
        IndexError,
        TypeError,
        ValueError
    ):
        app.logger.exception("Gemini request failed")
        return None


# Home page
@app.get("/")
def home():
    return render_template("index.html")


# Health check

@app.get("/api/check-gemini-config")
def check_gemini_config():
    return jsonify({
        "gemini_key_configured": bool(
            os.environ.get("GEMINI_API_KEY", "").strip()
        )
    })



# Suggested questions
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


# Main chatbot route
@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}

    question = (payload.get("message") or "").strip()

    if not question:
        return jsonify({
            "error": "Please type a question first."
        }), 400

    if len(question) > 1000:
        return jsonify({
            "error": "Please keep your question under 1,000 characters."
        }), 400

    # Step 1: Search the FAQ database
    faq, confidence = find_best_answer(question)

    if faq is not None:
        # Use the matching FAQ answer
        answer = faq.answer
        faq_id = faq.id
        category = faq.category or "General"

    else:
        # Step 2: Ask Gemini if no FAQ matches
        answer = get_gemini_answer(question)
        faq_id = None
        category = "AI Generated"

        # Step 3: Fallback if Gemini is unavailable
        if answer is None:
            answer = (
                "Sorry, I couldn't find an answer right now. "
                "Please try again later or contact the "
                "college office for confirmation."
            )
            category = "Not found"

    # Save chat history
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
        app.logger.exception("Could not save chat log")

    # Return answer to the frontend
    return jsonify({
        "answer": answer,
        "category": category,
        "confidence": round(confidence, 3),
        "matched": faq is not None
    })


# Initialize database
with app.app_context():
    db.create_all()
    seed_database()


# Start Flask application
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=False
    )
