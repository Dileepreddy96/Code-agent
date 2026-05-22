# CodeAgent AI 🤖

CodeAgent AI is a modern, high-density, Zero-Fluff Code Review Agent built for developers and engineering teams. It leverages **Google's Gemini 2.5 Flash** model to analyze code diffs, instantly detecting security flaws, $O(N^2)$ performance bottlenecks, and unpythonic anti-patterns before they reach production.

![Dashboard Preview](https://via.placeholder.com/1200x600.png?text=Smart+Code+Review+Agent)

## 🚀 Features

- **Strict Structured Outputs:** Uses Pydantic and the native Gemini structured output configuration to guarantee reliable JSON payloads without markdown hallucination.
- **Automated Webhooks:** Native `/webhook/github` endpoint to automatically intercept and review GitHub Pull Requests.
- **SaaS Rate Limiting:** Tiered usage limits (Anonymous, Trial, Basic, Pro) tracked robustly via SQLAlchemy.
- **OAuth Authentication:** Seamless GitHub OAuth integration via FastAPI routers and secure HTTP-only JSON Web Tokens (JWT).
- **Dynamic Pricing Localization:** Frontend UI automatically detects the user's timezone to adapt pricing between USD and INR organically.
- **Modern UI/UX:** A stunning, responsive Landing Page and Dashboard built with pure TailwindCSS and vanilla JS.

## 🛠️ Technology Stack

- **Backend:** Python 3.10+, FastAPI, Uvicorn
- **AI Integration:** `google-genai` SDK (Gemini 2.5 Flash)
- **Database:** PostgreSQL (via SQLAlchemy / `psycopg2`)
- **Authentication:** `PyJWT`, `httpx` (GitHub OAuth)
- **Frontend:** HTML5, TailwindCSS (CDN), Vanilla JavaScript

## ⚙️ Quickstart (Local Development)

### 1. Clone the repository
```bash
git clone https://github.com/Dileepreddy96/Code-agent.git
cd Code-agent
```

### 2. Install Dependencies
Ensure you have a modern Python 3 environment active, then install the required packages:
```bash
pip install fastapi uvicorn pydantic google-genai sqlalchemy psycopg2-binary httpx PyJWT python-dotenv
```

### 3. Environment Configuration
Create a `.env` file in the root directory and populate it with your credentials:
```env
GEMINI_API_KEY=your_gemini_api_key_here
GITHUB_CLIENT_ID=your_github_oauth_client_id
GITHUB_CLIENT_SECRET=your_github_oauth_client_secret
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/codeagent
```
*(Note: If `GEMINI_API_KEY` is omitted, the app gracefully falls back to a Mock Demo Mode).*

### 4. Run the Server
Launch the backend server using Uvicorn:
```bash
python -m uvicorn main:app --reload
```

The application will be live at **http://127.0.0.1:8000/**.

## 🛡️ Zero-Fluff AI Persona
CodeAgent AI strictly adheres to the following review criteria:
1. **Logic & Edge Cases:** Identifies race conditions, improper error handling, or off-by-one errors.
2. **Security:** Flags SQL injection, insecure secret handling, and unsafe `eval()` calls.
3. **Performance:** Highlights unoptimized loops or redundant database queries.
4. **Pythonic Patterns:** Suggests list comprehensions, context managers, and structural pattern matching.

---
*Developed by Dileep Reddy.*