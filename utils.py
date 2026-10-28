import os
import json
import re
import time
from typing import Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError

# For client setup
def get_client() -> genai.Client:
    """Initialize and return the Google GenAI client using the API key from env."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY not found. "
            "Please set it in your .env file or environment variables."
        )
    return genai.Client(api_key=api_key)

# CORE API CALL 

def call_gemini(
    prompt: str,
    system: str = "You are SmartStudy AI, a helpful academic assistant.",
    max_tokens: int = 4096,
    retries: int = 2
) -> str:
    """Send a prompt to Gemini and return the raw text response.Retries on failure up to `retries` times."""
    client = get_client()

    for attempt in range(retries + 1):
        try:
            # Configure system instructions using Google GenAI types config
            config = types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
            )

            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=config
            )
            return response.text

        except APIError as e:
            # Check for rate limiting or general API issues
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                if attempt < retries:
                    wait = 2 ** attempt  # exponential backoff: 1s, 2s
                    time.sleep(wait)
                    continue
            raise RuntimeError(f"Gemini API error: {str(e)}")
        
        except Exception as e:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Unexpected error communicating with Gemini: {str(e)}")

    return ""

# JSON PARSING & VALIDATION 

def extract_json(raw: str) -> dict:
    """
    Extract and parse a JSON object from Gemini's raw response.
    Handles cases where the model accidentally adds markdown fences or leading text.
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try finding the first { ... } block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # If all else fails, return an error dict
    return {
        "error": "Failed to parse JSON from model response.",
        "raw_response": raw[:500]  # truncate for display
    }


def validate_plan(data: dict) -> tuple[bool, list[str]]:
    """
    Validate that a study plan JSON has all required top-level fields.
    Returns (is_valid, list_of_missing_fields).
    """
    required = ["plan_title", "total_days", "daily_hours", "goal", "days", "overall_tips"]
    missing  = [f for f in required if f not in data]
    return (len(missing) == 0), missing


def validate_explanation(data: dict) -> tuple[bool, list[str]]:
    """
    Validate that a concept explanation JSON has all required fields.
    Returns (is_valid, list_of_missing_fields).
    """
    required = [
        "concept", "simple_definition", "detailed_explanation",
        "key_points", "study_tips", "difficulty_rating"
    ]
    missing = [f for f in required if f not in data]
    return (len(missing) == 0), missing