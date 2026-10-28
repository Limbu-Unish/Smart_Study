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

# FORMATTING HELPERS

def format_plan_as_text(plan: dict) -> str:
    """
    Convert a parsed study plan JSON into clean, readable text for display.
    """
    if "error" in plan:
        return f"Error: {plan['error']}\n\nRaw response:\n{plan.get('raw_response', '')}"

    lines = []
    lines.append(f" {plan.get('plan_title', 'Study Plan')}")
    lines.append(f" Goal: {plan.get('goal', 'N/A')}")
    lines.append(f"  Daily Hours: {plan.get('daily_hours', 'N/A')}  |   Total Days: {plan.get('total_days', 'N/A')}")
    lines.append(f"  Tone: {plan.get('tone', 'N/A')}  |  Language: {plan.get('language', 'N/A')}")

    if plan.get("warning"):
        lines.append(f"\n  Note: {plan['warning']}")

    lines.append("\n" + "─" * 60)

    for day in plan.get("days", []):
        # Get date label, or fallback to "Day X" if missing
        date_label = day.get('date_label') or f"Day {day.get('day', '?')}"
        lines.append(f"\n{date_label}")
        lines.append(f"Focus: {day.get('focus_topic', 'N/A')}")
        lines.append(f"Daily Goal: {day.get('daily_goal', 'N/A')}")
        lines.append(f"Breaks: {day.get('break_schedule', 'N/A')}")
        lines.append("")

        for s in day.get("sessions", []):
            lines.append(f"Session {s.get('session_number', '?')} — {s.get('time_slot', 'N/A')}")
            lines.append(f"Topic    : {s.get('topic', 'N/A')}")
            lines.append(f"Activity  : {s.get('activity', 'N/A')}")
            lines.append(f"Duration  : {s.get('duration_minutes', 'N/A')} minutes")
            resources = s.get("resources", [])
            if resources:
                lines.append(f"Resources : {', '.join(resources)}")
            lines.append("")

        lines.append(f" {day.get('motivation_tip', '')}")
        lines.append("─" * 60)

    tips = plan.get("overall_tips", [])
    if tips:
        lines.append("\n Overall Study Tips:")
        for i, tip in enumerate(tips, 1):
            lines.append(f"  {i}. {tip}")

    return "\n".join(lines)