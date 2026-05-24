import os
import logging
import asyncio
from dotenv import load_dotenv

# Load environment variables from .env file immediately
load_dotenv()

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from datetime import date
from database import get_db, User, UsageLog, CodeReviewHistory
import json
from auth import router as auth_router

from pydantic import ValidationError
from google import genai
from google.genai import types

# Import the existing setup from reviewer.py
from reviewer import SYSTEM_PROMPT, CodeReviewResponse, generate_user_prompt

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI App
app = FastAPI(title="Smart Code Review Agent")

# Enable CORS for frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

# ---------------------------------------------------------
# App Setup & GenAI Client Initialization
# ---------------------------------------------------------
# Read the API key from the environment.
# You can place this in a .env file and load it using python-dotenv, 
# or set it in your terminal before running:
# Windows: $env:GEMINI_API_KEY="your-api-key"
api_key = os.getenv("GEMINI_API_KEY")

# Initialize the Google GenAI SDK client
client = genai.Client() if api_key else None

@app.on_event("startup")
async def startup_event():
    if not client:
        logger.warning("GEMINI_API_KEY is not set. AI review endpoint will fail until configured.")
    else:
        logger.info("Smart Code Review Agent is starting up with Gemini API.")

# ---------------------------------------------------------
# Frontend Dashboard Routes
# ---------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the main frontend dashboard.html"""
    html_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="dashboard.html not found")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.post("/api/review")
async def manual_review(request: Request, db: Session = Depends(get_db)):
    """
    Handles manual code review requests from the frontend dashboard.
    Expects JSON: { "code_diff": "...", "username": "optional_mock_user" }
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    code_diff = payload.get("code_diff", "").strip()
    username = payload.get("username")
    language = payload.get("language")

    if not language:
        raise HTTPException(status_code=400, detail="Programming language must be selected")

    if not code_diff:
        raise HTTPException(status_code=400, detail="code_diff cannot be empty")

    def validate_language(lang: str, code: str) -> bool:
        if lang == "Python":
            if ('public class' in code or 'const ' in code) and 'def ' not in code:
                return False
        elif lang == "Java":
            if ('def ' in code or 'console.log' in code) and 'public class' not in code and 'System.out.' not in code:
                return False
        elif "JavaScript" in lang:
            if ('def ' in code or 'public class' in code) and 'function' not in code and 'const ' not in code:
                return False
        return True

    if not validate_language(language, code_diff):
        raise HTTPException(
            status_code=400,
            detail=f"Validation Error: The code content provided does not match your selected language ({language}). Please verify your syntax or select the correct language option."
        )

    line_count = len(code_diff.splitlines())

    if not username:
        if line_count > 50:
            raise HTTPException(status_code=403, detail="Anonymous users are limited to 50 lines. Please sign up to review larger files.")
    else:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            # Create mock user if doesn't exist, defaulting to Trial
            user = User(username=username, tier="Trial")
            db.add(user)
            db.commit()
            db.refresh(user)

        if user.tier != "Pro":
            usage = db.query(UsageLog).filter(UsageLog.user_id == user.id, UsageLog.date == date.today()).first()
            if not usage:
                usage = UsageLog(user_id=user.id, date=date.today(), review_count=0)
                db.add(usage)
                db.commit()
                db.refresh(usage)
            
            limit = 5 if user.tier == "Trial" else 50
            if usage.review_count >= limit:
                raise HTTPException(status_code=429, detail=f"{user.tier} tier limit reached ({limit}/day). Please upgrade for more.")
            
            usage.review_count += 1
            db.commit()

    logger.info("Received manual review request from dashboard")
    
    try:
        # Run the AI review asynchronously
        review_result = await analyze_code_diff("Manual Dashboard Submission", code_diff)
        
        # Save history to DB
        history_record = CodeReviewHistory(
            user_id=user.id if username and user else None,
            input_code=code_diff,
            summary=review_result.summary,
            issues_json=json.dumps([issue.model_dump() for issue in review_result.issues])
        )
        db.add(history_record)
        db.commit()

        return {"status": "success", "review": review_result.model_dump()}
    except Exception as e:
        # Return a safe 400 JSON response so the frontend can display the actual error string
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=400, content={"detail": str(e), "error": str(e)})

@app.get("/api/reviews/history")
async def get_review_history(db: Session = Depends(get_db)):
    """Fetches the 20 most recent reviews."""
    history = db.query(CodeReviewHistory).order_by(CodeReviewHistory.timestamp.desc()).limit(20).all()
    results = []
    for record in history:
        issues = []
        if record.issues_json:
            try:
                issues = json.loads(record.issues_json)
            except Exception:
                pass
        results.append({
            "id": record.id,
            "timestamp": record.timestamp.isoformat() if record.timestamp else None,
            "summary": record.summary,
            "input_code": record.input_code,
            "issues": issues
        })
    return {"status": "success", "history": results}

# ---------------------------------------------------------
# Webhook Handling Logic
# ---------------------------------------------------------
@app.post("/webhook/github")
async def github_webhook(request: Request):
    """
    Receives incoming JSON payloads from GitHub webhooks.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Extract relevant fields. Real GitHub webhooks have deeply nested structures,
    # and code diffs are typically fetched using the PR's diff_url. 
    # For this architecture, we extract what is needed.
    repo_name = payload.get("repository", {}).get("full_name", "unknown/repo")
    pr_id = payload.get("pull_request", {}).get("number", "unknown")
    
    # We simulate extracting the diff directly from the payload here.
    code_diff = payload.get("code_diff", "")

    if not code_diff:
        logger.warning(f"No code diff found for PR #{pr_id} in {repo_name}")
        return {"status": "skipped", "reason": "No code diff provided in payload"}

    logger.info(f"Received review request for PR #{pr_id} in {repo_name}")
    
    # Run the AI review asynchronously
    review_result = await analyze_code_diff(repo_name, code_diff)
    
    if review_result:
        # Success: Return the Pydantic model dumped to a dict
        return {"status": "success", "review": review_result.model_dump()}
    else:
        # If the LLM failed, we raise a 500 error gracefully
        raise HTTPException(status_code=500, detail="Code review analysis failed.")

# ---------------------------------------------------------
# AI Review Service Layer & Graceful Error Handling
# ---------------------------------------------------------
async def analyze_code_diff(repo_name: str, code_diff: str) -> CodeReviewResponse:
    """
    Sends the code diff to the LLM and forces a structured CodeReviewResponse output.
    """
    if not client:
        # Fallback to Mock Data Mode
        from reviewer import ReviewIssue
        return CodeReviewResponse(
            summary="Review running in offline demo mode. Please add your GEMINI_API_KEY to your .env file for live AI analysis.",
            issues=[
                ReviewIssue(
                    line_number=1,
                    severity="Warning",
                    category="Security",
                    description="[MOCK] Hardcoded API key detected in diff.",
                    suggested_fix="import os\napi_key = os.getenv('API_KEY')"
                ),
                ReviewIssue(
                    line_number=5,
                    severity="Style",
                    category="Pythonic Patterns",
                    description="[MOCK] Consider using a list comprehension here for better readability.",
                    suggested_fix="data = [x for x in items if x]"
                )
            ]
        )

    # Generate the dynamic user prompt using the function from reviewer.py
    user_prompt = generate_user_prompt(
        file_name="Multiple Files (PR Diff)",
        project_type=f"GitHub Repository: {repo_name}",
        code_diff=code_diff
    )

    try:
        # Force structured output directly at the network layer
        # Switching to gemini-2.5-flash to avoid the very strict free tier limits of Pro (2 RPM)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[SYSTEM_PROMPT, f"Review this code:\n{code_diff}"],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CodeReviewResponse,
            ),
        )
        
        # Because we used response_schema, response.text should be pure JSON
        return CodeReviewResponse.model_validate_json(response.text)

    except ValidationError as e:
        # Catch unexpected schema hallucinations
        raise Exception(f"LLM Validation Error: Response did not match the expected JSON schema. Details: {e}")
    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            from reviewer import ReviewIssue
            return CodeReviewResponse(
                summary="⚠️ Gemini API Rate Limit Reached (429). The model is busy. Please wait 60 seconds and try again.",
                issues=[
                    ReviewIssue(
                        line_number=0,
                        severity="Warning",
                        category="Rate Limit",
                        description="Google Gemini API free tier limits exhausted.",
                        suggested_fix="Try again in a few moments."
                    )
                ]
            )
        # Catch network timeouts, rate limits, or API errors
        raise Exception(f"LLM API Error: Failed to communicate with Gemini. Details: {e}")

if __name__ == "__main__":
    import uvicorn
    # Run the server on port 8000
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
