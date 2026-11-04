# app.py
# Importing the essential libraries
import os
import json
import gradio as gr
from dotenv import load_dotenv

from prompts import STUDY_PLANNER_PROMPT, CONCEPT_EXPLAINER_PROMPT, FOLLOWUP_PROMPT
from utils import (
    call_gemini,
    extract_json,
    validate_plan,
    validate_explanation,
    format_plan_as_text,
    format_explanation_as_text,
    format_followup_as_text,
    build_history_string,
    sanitize_input,
    validate_hours,
)

# Load environment variables from .env file
load_dotenv()

# CONVERSATION MEMORY (in-session state) 
# Stored as a list of {"role": "user"/"assistant", "content": "..."}
conversation_history = []


#FEATURE 1: STUDY PLANNER

def generate_study_plan(
    subjects: str,
    hours: float,
    goal: str,
    tone: str,
    language: str,
    length: str,
    notes: str
) -> tuple[str, str]:
    """
    Generate a personalized study plan using geminireturns (formatted_text_output, raw_json_output).
    """
    #Input validation
    subjects = sanitize_input(subjects)
    goal     = sanitize_input(goal)
    notes    = sanitize_input(notes)

    if not subjects.strip():
        return "Please enter at least one subject or topic.", "{}"

    valid_hours, hours_msg = validate_hours(hours)
    if not valid_hours:
        return f"{hours_msg}", "{}"

    #Build and send prompt
    length_map = {"Short (1 Day)": "short", "Medium (3 Days)": "medium", "Long (7 Days)": "long"}
    prompt = STUDY_PLANNER_PROMPT.format(
        subjects=subjects,
        hours=hours,
        goal=goal or "General revision",
        tone=tone.lower(),
        language=language,
        length=length_map.get(length, "short"),
        notes=notes or "None"
    )

    try:
        raw      = call_gemini(prompt)
        parsed   = extract_json(raw)
        is_valid, missing = validate_plan(parsed)

        if not is_valid:
            return (
                f"Plan generated but missing fields: {missing}\n\n"
                + format_plan_as_text(parsed),
                json.dumps(parsed, indent=2, ensure_ascii=False)
            )

        # Add to conversation memory
        conversation_history.append({
            "role": "user",
            "content": f"Generate a study plan for: {subjects}, {hours} hours/day, goal: {goal}"
        })
        conversation_history.append({
            "role": "assistant",
            "content": f"Study plan generated for {parsed.get('total_days', '?')} days."
        })

        return (
            format_plan_as_text(parsed),
            json.dumps(parsed, indent=2, ensure_ascii=False)
        )

    except ValueError as e:
        return f"Configuration Error: {str(e)}", "{}"
    except RuntimeError as e:
        return f"API Error: {str(e)}", "{}"
    except Exception as e:
        return f"Unexpected error: {str(e)}", "{}"

# FEATURE 2: CONCEPT EXPLAINER 

def explain_concept(
    concept: str,
    level: str,
    tone: str,
    language: str,
    use_analogy: bool,
    use_example: bool,
    context: str
) -> tuple[str, str]:
    """
    Explain a concept using Gemini with structured JSON output.
    Returns (formatted_text_output, raw_json_output).
    """
    concept = sanitize_input(concept, max_length=300)
    context = sanitize_input(context, max_length=300)

    if not concept.strip():
        return "Please enter a concept to explain.", "{}"

    prompt = CONCEPT_EXPLAINER_PROMPT.format(
        concept=concept,
        level=level.lower(),
        tone=tone.lower(),
        language=language,
        use_analogy="yes" if use_analogy else "no",
        use_example="yes" if use_example else "no",
        context=context or "None provided"
    )

    try:
        raw    = call_gemini(prompt)
        parsed = extract_json(raw)
        is_valid, missing = validate_explanation(parsed)

        if not is_valid:
            return (
                f"Explanation generated but missing fields: {missing}\n\n"
                + format_explanation_as_text(parsed),
                json.dumps(parsed, indent=2, ensure_ascii=False)
            )

        # Add to conversation memory
        conversation_history.append({
            "role": "user",
            "content": f"Explain the concept: {concept} at {level} level in {language}"
        })
        conversation_history.append({
            "role": "assistant",
            "content": parsed.get("simple_definition", "Concept explained.")
        })

        return (
            format_explanation_as_text(parsed),
            json.dumps(parsed, indent=2, ensure_ascii=False)
        )

    except ValueError as e:
        return f"Configuration Error: {str(e)}", "{}"
    except RuntimeError as e:
        return f"API Error: {str(e)}", "{}"
    except Exception as e:
        return f"Unexpected error: {str(e)}", "{}"