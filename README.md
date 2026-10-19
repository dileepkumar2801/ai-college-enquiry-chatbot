# CampusMate — AI-Based College Enquiry Chatbot

A Flask web application with a responsive HTML/CSS/JavaScript chat UI, TF-IDF + cosine-similarity question matching, and a SQL database for FAQs and chat logs.

## Features

- Responsive mobile and desktop chat interface
- NLP-based matching using scikit-learn TF-IDF and cosine similarity
- FAQ database seeded from `faq_data.json`
- Chat history stored in the database
- JSON endpoints: `/api/chat`, `/api/suggestions`, `/api/health`
- Conservative fallback when no reliable FAQ match is found
- SQLite locally; PostgreSQL supported using `DATABASE_URL`

> The included FAQ answers are placeholders for demonstration. Replace them with verified information from your own college before publishing.

## 1. Run locally

Install Python 3.10+ (Python 3.12 recommended).

Open a terminal in this project folder:

```bash
python -m venv .venv
```

Activate it:

**Windows PowerShell**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows Command Prompt**
```bat
.venv\Scripts\activate.bat
```

**macOS/Linux**
```bash
source .venv/bin/activate
```

Install dependencies and start the app:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` in your browser. Keep the terminal running while you use it.

Do not open `templates/index.html` directly or use Live Server for the app: Flask serves the page and handles the `/api/chat` endpoint.

## 2. Add your college's real information

Edit `faq_data.json`. Each item has:
- `question`: the canonical question
- `answer`: a verified answer
- `category`: category shown in chat
- `keywords`: alternate terms students might use

Example:

```json
{
  "question": "What are the college working hours?",
  "answer": "The college office is open from 9:00 AM to 4:30 PM, Monday to Saturday. Confirm holidays on the official notice board.",
  "category": "General",
  "keywords": ["timings", "hours", "opening", "working days"]
}
```

The database is seeded only when it contains zero FAQs. If you edit `faq_data.json` after the database has already been created, the old rows will not be overwritten. For a fresh local demo, stop the app, back up anything important, delete `college_chatbot.db` (typically under the `instance` folder), then restart the app. On a hosted database, use a database administration tool or add an authenticated admin feature before editing records.

Use only public/approved college information. Do not add student records, private phone numbers, passwords, or other confidential information.

## 3. API quick test

Health check:

```bash
curl http://127.0.0.1:5000/api/health
```

Chat request:

```bash
curl -X POST http://127.0.0.1:5000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"How can I apply for admission?\"}"
```

## 4. Deploy online using Render

1. Create a GitHub account if you do not have one.
2. Create a new GitHub repository and upload these project files. Do not upload `.venv`, `.env`, or database files.
3. Sign in to Render and create a **Web Service** from your repository.
4. Select the Python runtime. Use:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
5. Add environment variable `SECRET_KEY` with a long random value. Render can generate one for you.
6. Deploy. The app's public URL will be shown by Render.

### Database persistence for public deployment

The default SQLite database is suitable for local learning, but free web-service filesystems may be ephemeral. Data stored in a local SQLite file may be lost when a hosted service restarts or redeploys.

For persistent online data, create a free PostgreSQL database with a provider that currently offers a free tier (for example, Neon, subject to its current terms). Copy its connection string into your Render web service as the `DATABASE_URL` environment variable, using the provider's SSL-enabled URL. Redeploy after setting it. The app automatically uses PostgreSQL when `DATABASE_URL` is set.

Free plans, quotas, sleep behavior, and availability can change. Check the hosting provider's current terms before relying on a free deployment.

## 5. Important limitations

- This is retrieval-based NLP, not a generative LLM. It returns answers from the FAQ database.
- The match score is a similarity score, not a calibrated probability of correctness.
- Tune `MATCH_THRESHOLD` in the environment if it accepts unrelated questions or rejects valid ones.
- The demo does not include a public admin login. Do not expose a write endpoint without authentication and authorization.
- Verify fees, admissions, dates, contacts, and policies against official college sources before publishing.
