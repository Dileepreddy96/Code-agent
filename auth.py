import os
import httpx
import jwt
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db, User

router = APIRouter(prefix="/auth")

# Environment variables for OAuth
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "your_github_client_id")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "your_github_client_secret")

# JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key-for-local-dev-only")
JWT_ALGORITHM = "HS256"

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=14)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

@router.get("/login/github")
async def login_github():
    """Redirects the user to GitHub's OAuth authorization page."""
    redirect_uri = "http://127.0.0.1:8000/auth/callback/github"
    github_auth_url = f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&redirect_uri={redirect_uri}&scope=read:user user:email"
    return RedirectResponse(url=github_auth_url)

@router.get("/callback/github")
async def auth_github_callback(code: str, db: Session = Depends(get_db)):
    """Handles the GitHub OAuth callback, fetches user info, and issues a JWT."""
    
    # 1. Exchange the code for an access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
            },
        )
    
    token_data = token_response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to retrieve access token from GitHub")

    # 2. Fetch the user's profile from GitHub
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        emails_response = await client.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
    github_user = user_response.json()
    emails = emails_response.json()
    
    # Find primary email
    primary_email = next((email["email"] for email in emails if email["primary"]), None)
    
    github_id = str(github_user.get("id"))
    full_name = github_user.get("name") or github_user.get("login")
    avatar_url = github_user.get("avatar_url")
    
    # 3. Upsert User in PostgreSQL database
    user = db.query(User).filter(User.github_id == github_id).first()
    
    if not user:
        # User doesn't exist, create them
        user = User(
            github_id=github_id,
            email=primary_email,
            full_name=full_name,
            avatar_url=avatar_url,
            current_tier="Trial"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Optionally update avatar or email if they changed
        user.avatar_url = avatar_url
        user.full_name = full_name
        db.commit()

    # 4. Generate JWT
    jwt_token = create_access_token({"sub": str(user.id), "tier": user.current_tier})
    
    # 5. Redirect to Dashboard with the token in a secure cookie
    response = RedirectResponse(url="/dashboard")
    response.set_cookie(
        key="access_token", 
        value=f"Bearer {jwt_token}", 
        httponly=True,
        max_age=14 * 24 * 60 * 60, # 14 days
        samesite="lax",
    )
    return response
