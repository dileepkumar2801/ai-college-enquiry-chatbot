# SRIT Assist — AI College Enquiry Chatbot

A responsive, deployment-ready enquiry chatbot for **Srinivasa Ramanujan Institute of Technology (SRIT), Ananthapuramu**, built from the SRIT homepage HTML supplied for this project.

## What is included

- A polished, mobile-friendly chat UI with suggested questions, typing state, clear-chat control and official-page shortcuts.
- Flask backend API (`/api/chat`) and health check (`/api/health`).
- Optional server-side Gemini API integration. The API key is never sent to the browser.
- A curated SRIT knowledge base with a simple retrieval step and answers that link to the official site.
- Graceful fallback when the Gemini key is missing, the model/API is unavailable, or API quota is exhausted. College-specific values that are not present in the supplied homepage (for example current fees or cutoffs) are not invented.
- Basic request validation, request size limits, per-process rate limiting, safe text rendering and context-size limits.
- `render.yaml` for Render configuration and a `.env.example` template.

## Deploy online on Render

This project is prepared for Render, but it is **not deployed to a public URL automatically by downloading this ZIP**. To publish it, put the project in a GitHub repository and connect that repository to Render.

1. Download and unzip this project.
2. Create a new **public or private GitHub repository** and upload the contents of this folder (the files inside `srit-ai-college-enquiry`, not the parent folder).
3. In Render, choose **New → Web Service**, connect your GitHub repository, and use these settings:
   - **Runtime:** Python  
   - **Build command:** `pip install -r requirements.txt`  
   - **Start command:** `gunicorn --workers 1 --threads 4 --timeout 60 app:app`  
   - **Health check path:** `/api/health`
4. In the Render service's **Environment** section, add:
   - `GEMINI_API_KEY` = your key from [Google AI Studio](https://aistudio.google.com/app/apikey)
   - `GEMINI_MODEL` = `gemini-3.8-flash` (if this model is unavailable to your API key/project, set a supported text model listed for your key)
   - `RATE_LIMIT_PER_MINUTE` = `18` (optional)
5. Deploy. When the deployment completes, open the `onrender.com` URL Render gives you.

The included `render.yaml` can also be used as a Blueprint configuration. Set the API key as a secret/environment variable in Render; **never add a real key to GitHub or to `static/app.js`**.

### Important about free tiers and API credits

- Render's free web service may sleep after inactivity and can take a little time to wake up.
- The app itself can run in **Knowledge mode without a Gemini key**. It can answer the main predefined enquiry categories from the supplied snapshot and link to official pages.
- To enable AI-generated answers, a valid key and available API quota are required. If Gemini returns an error or quota limit, the app falls back to saved SRIT knowledge rather than stopping the whole website. This fallback is useful but is not a replacement for a fully available AI provider.

## Local test (optional)

Python 3.10+ is recommended.

**Windows PowerShell**

```powershell
cd srit-ai-college-enquiry
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:GEMINI_API_KEY="YOUR_KEY_HERE"
$env:GEMINI_MODEL="gemini-3.8-flash"
python app.py
```

**macOS / Linux**

```bash
cd srit-ai-college-enquiry
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY="YOUR_KEY_HERE"
export GEMINI_MODEL="gemini-3.8-flash"
python app.py
```

Open `http://127.0.0.1:5000`. Leave `GEMINI_API_KEY` unset to test the knowledge fallback.

Run the included smoke tests with:

```bash
python -m unittest discover -s tests -v
```

## How it answers

1. The browser sends the question to the Flask server.
2. The server searches the bundled SRIT notes for relevant topics.
3. If `GEMINI_API_KEY` is configured, the server calls Gemini with the question, limited recent chat history and relevant SRIT notes.
4. If AI is not configured or the provider fails, predefined knowledge answers and official SRIT URLs are used.
5. The browser stores the last few conversation turns in `sessionStorage` for that browser tab; the app does not create a server-side chat-history database.

## Source and accuracy notes

The knowledge base is based on the supplied SRIT homepage HTML, not on a live crawl. The snapshot contains navigation for courses, admissions, fee structure, scholarships, examination information, campus facilities and placement statistics. It lists historical **2024–25** placement figures; these are labelled historical in the chatbot. Current fees, eligibility, cutoffs, seat availability, deadlines, hostel charges, transport routes and current regulatory status should be verified on the official SRIT website.

The homepage source displays the contact number `91-951 561 1111` and email `hr@srit.ac.in`. Use the [official Contact Us page](https://www.srit.ac.in/contact-us/) to verify current contact and postal details.

## Project structure

```text
srit-ai-college-enquiry/
├── app.py
├── requirements.txt
├── render.yaml
├── .env.example
├── data/
│   └── college_knowledge.json
├── templates/
│   └── index.html
├── static/
│   ├── styles.css
│   └── app.js
└── tests/
    └── test_app.py
```

## Limitations

- This is an enquiry assistant, not an official SRIT system. It does not submit applications, process payments or retrieve private examination results.
- Rate limiting is in-process. For a high-traffic production deployment, use a shared rate limiter, monitoring, stronger abuse prevention and approved institutional data sources.
- Live website contents are not automatically refreshed. Update `data/college_knowledge.json` whenever the official information changes.

## Fixing `FileNotFoundError: data/college_knowledge.json` on Render

The app now searches the expected `data/` path, a root-level copy, and common nested-folder layouts. If the file was omitted from the GitHub repository, it uses a bundled copy of the knowledge base so the service can still start.

For the preferred setup, the GitHub repository should contain `app.py` and the `data/college_knowledge.json` file at the same repository level as shown below:

```text
repository-root/
├── app.py
├── data/
│   └── college_knowledge.json
├── templates/
├── static/
├── requirements.txt
└── render.yaml
```

If your Render service uses a **Root Directory** value, set it to the folder containing `app.py`, `data/`, `templates/`, and `requirements.txt`. If you need a custom JSON path, set `COLLEGE_KNOWLEDGE_PATH` in Render Environment settings. After updating GitHub, trigger **Manual Deploy → Deploy latest commit**.

