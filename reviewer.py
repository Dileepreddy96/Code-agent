import json
from pydantic import BaseModel, Field
from typing import List, Literal

# 1. The System Prompt (The Agent's Brain)
# This prompt should be stored as a constant in your Python code and passed to your LLM connector.
SYSTEM_PROMPT = """Role: You are a Senior Principal Software Engineer and Security Auditor. Your task is to perform a high-density, Zero-Fluff code review on the provided Python diff.

Analysis Criteria:
- Logic & Edge Cases: Identify race conditions, improper error handling, or off-by-one errors.
- Security: Check for SQL injection, insecure secret handling, or unsafe eval() calls.
- Performance: Highlight O(N^2) operations inside loops or redundant database queries.
- Pythonic Patterns: Suggest list comprehensions, context managers, or structural pattern matching where appropriate.

Output Requirements:
- Do NOT provide conversational filler (e.g., "Sure, I can help with that").
- Return ONLY a JSON object matching the requested schema.
- Each Issue MUST include line_number, severity (Critical, Warning, Style), category, description, and suggested_fix."""


# 2. The Implementation (Antigravity + Pydantic)
# To make this work in your code, you should define a Pydantic Model. 
# This ensures that if the AI hallucinates a field name, your Antigravity backend will catch the validation error.

class ReviewIssue(BaseModel):
    line_number: int
    severity: Literal["Critical", "Warning", "Style"]
    category: str = Field(description="e.g., Security, Performance, Logic")
    description: str
    suggested_fix: str

class CodeReviewResponse(BaseModel):
    issues: List[ReviewIssue]
    summary: str = Field(description="A 2-sentence overview of the PR health")


# 3. The User Prompt (The Work Order)
# This is what your code generates dynamically when a new PR arrives.

def generate_user_prompt(file_name: str, project_type: str, code_diff: str) -> str:
    """
    Generates the dynamic user prompt when a new PR arrives.
    """
    prompt = f"""Task: Review the following diff from {file_name}.
Context: This code is part of a {project_type}.

Code Diff:
```diff
{code_diff}
```

Instructions: Apply the Senior Engineer persona and return the review in the requested JSON schema."""
    return prompt


# --- Example Usage / Mock LLM Connector ---
if __name__ == "__main__":
    # Example diff that might trigger the reviewer
    sample_diff = '''
+ def get_user_data(db_conn, user_id):
+     # Possible SQL Injection
+     query = f"SELECT * FROM users WHERE id = {user_id}"
+     return db_conn.execute(query)
    '''
    
    print("=== SYSTEM PROMPT ===")
    print(SYSTEM_PROMPT)
    
    print("\n=== DYNAMIC USER PROMPT ===")
    user_prompt = generate_user_prompt(
        file_name="auth.py", 
        project_type="FastAPI Web Service", 
        code_diff=sample_diff
    )
    print(user_prompt)
    
    print("\n=== EXPECTED JSON OUTPUT SCHEMA ===")
    # Print the JSON schema so you can pass it to the LLM
    print(json.dumps(CodeReviewResponse.model_json_schema(), indent=2))
