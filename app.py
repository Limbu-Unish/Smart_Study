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


#FEATURE 3: FOLLOW-UP CHAT (CONVERSATION MEMORY)

def chat_followup(
    user_message: str,
    chat_history: list
) -> tuple[list, str]:
    """
    Handle follow-up questions using conversation memory.
    Maintains context from previous planner and explainer interactions.
    """
    user_message = sanitize_input(user_message, max_length=500)

    if not user_message.strip():
        chat_history.append(("", "Please type a message first."))
        return chat_history, ""

    # Build history string from global memory + current chat
    session_turns = [{"role": "user" if i % 2 == 0 else "assistant", "content": msg}
                     for i, (user_msg, bot_msg) in enumerate(chat_history)
                     for msg in [user_msg, bot_msg] if msg]
    all_history = conversation_history + session_turns

    history_str = build_history_string(all_history[-10:])  # last 10 turns for context

    prompt = FOLLOWUP_PROMPT.format(
        history=history_str,
        user_message=user_message
    )

    try:
        raw    = call_gemini(prompt, max_tokens=2048)
        parsed = extract_json(raw)

        if "error" in parsed:
            response_text = f"Error parsing response: {parsed['error']}"
        else:
            response_text = format_followup_as_text(parsed)

        chat_history.append((user_message, response_text))
        return chat_history, ""

    except ValueError as e:
        chat_history.append((user_message, f"Configuration Error: {str(e)}"))
        return chat_history, ""
    except RuntimeError as e:
        chat_history.append((user_message, f"API Error: {str(e)}"))
        return chat_history, ""
    except Exception as e:
        chat_history.append((user_message, f"Error: {str(e)}"))
        return chat_history, ""


def clear_chat():
    """Clear the chat history and global conversation memory."""
    global conversation_history
    conversation_history = []
    return [], ""


#GRADIO UI

def build_ui():
    with gr.Blocks(
        title="SmartStudy AI",
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="indigo",
            neutral_hue="slate"
        ),
        css="""
        .header-box { text-align: center; padding: 20px; }
        .tab-content { padding: 10px; }
        .output-box { font-family: monospace; font-size: 13px; }
        footer { display: none !important; }
        """
    ) as demo:

        # ── HEADER ────────────────────────────────────────────────────────────
        gr.HTML("""
        <div class='header-box'>
            <h1>🎓 SmartStudy AI</h1>
            <p style='color: #666; font-size: 16px;'>
                Your personal AI-powered study planner and concept explainer.
                <br>Supports <strong>English</strong> and <strong>Nepali (नेपाली)</strong> — for students everywhere.
            </p>
        </div>
        """)

        with gr.Tabs():

            # ── TAB 1: STUDY PLANNER ─────────────────────────────────────────
            with gr.Tab("Study Planner", elem_classes="tab-content"):
                gr.Markdown("### Generate a Personalized Study Plan")
                gr.Markdown(
                    "Enter your subjects, available time, and preferences — "
                    "SmartStudy AI will build a structured, realistic plan for you."
                )

                with gr.Row():
                    with gr.Column(scale=1):
                        plan_subjects = gr.Textbox(
                            label="Subject(s) / Topic(s)",
                            placeholder="e.g. Machine Learning, Python, Data Structures",
                            lines=2
                        )
                        plan_hours = gr.Slider(
                            label="Daily Study Hours",
                            minimum=1, maximum=12, step=0.5, value=4
                        )
                        plan_goal = gr.Textbox(
                            label="Study Goal",
                            placeholder="e.g. Prepare for exam next week, complete project, revise semester",
                            lines=2
                        )
                        with gr.Row():
                            plan_tone = gr.Dropdown(
                                label="Tone",
                                choices=["Friendly", "Strict", "Motivational"],
                                value="Friendly"
                            )
                            plan_language = gr.Dropdown(
                                label="Language",
                                choices=["English", "Nepali", "Both"],
                                value="English"
                            )
                        plan_length = gr.Radio(
                            label="Plan Length",
                            choices=["Short (1 Day)", "Medium (3 Days)", "Long (7 Days)"],
                            value="Short (1 Day)"
                        )
                        plan_notes = gr.Textbox(
                            label="Additional Notes (optional)",
                            placeholder="e.g. I am weak in calculus, prefer evenings, have a test on Day 3",
                            lines=2
                        )
                        plan_btn = gr.Button("Generate Study Plan", variant="primary", size="lg")

                    with gr.Column(scale=2):
                        plan_output = gr.Textbox(
                            label="Your Study Plan",
                            lines=30,
                            interactive=False,
                            elem_classes="output-box"
                        )
                        with gr.Accordion("Raw JSON Output (for developers)", open=False):
                            plan_json = gr.Code(language="json", label="Structured JSON", lines=20)

                plan_btn.click(
                    fn=generate_study_plan,
                    inputs=[plan_subjects, plan_hours, plan_goal, plan_tone,
                            plan_language, plan_length, plan_notes],
                    outputs=[plan_output, plan_json]
                )

                gr.Examples(
                    examples=[
                        ["Machine Learning, Python", 4, "Prepare for final exam in 3 days",
                         "Motivational", "English", "Medium (3 Days)", "I struggle with neural networks"],
                        ["गणित, विज्ञान", 3, "परीक्षाको तयारी", "Friendly", "Nepali",
                         "Short (1 Day)", ""],
                        ["Data Structures, Algorithms", 6, "Technical interview preparation",
                         "Strict", "English", "Long (7 Days)", "Focus on trees and graphs"],
                    ],
                    inputs=[plan_subjects, plan_hours, plan_goal, plan_tone,
                            plan_language, plan_length, plan_notes],
                    label="📌 Try These Examples"
                )

            #TAB 2: CONCEPT EXPLAINER
            with gr.Tab("Concept Explainer", elem_classes="tab-content"):
                gr.Markdown("### Understand Any Concept — Clearly & Deeply")
                gr.Markdown(
                    "Enter any concept from any subject — SmartStudy AI will explain it "
                    "at your level, with analogies, examples, and study tips."
                )

                with gr.Row():
                    with gr.Column(scale=1):
                        exp_concept = gr.Textbox(
                            label="Concept to Explain",
                            placeholder="e.g. Backpropagation, Photosynthesis, Supply and Demand, Karma",
                            lines=2
                        )
                        exp_context = gr.Textbox(
                            label="Additional Context (optional)",
                            placeholder="e.g. I'm a first-year CS student | This is for a biology exam",
                            lines=2
                        )
                        with gr.Row():
                            exp_level = gr.Dropdown(
                                label="🎓 Explanation Level",
                                choices=["Beginner", "Intermediate", "Advanced"],
                                value="Beginner"
                            )
                            exp_tone = gr.Dropdown(
                                label="Tone",
                                choices=["Friendly", "Strict", "Motivational"],
                                value="Friendly"
                            )
                        exp_language = gr.Dropdown(
                            label="Language",
                            choices=["English", "Nepali", "Both"],
                            value="English"
                        )
                        with gr.Row():
                            exp_analogy = gr.Checkbox(label="Include Analogy", value=True)
                            exp_example = gr.Checkbox(label="Include Real-World Example", value=True)

                        exp_btn = gr.Button("Explain Concept", variant="primary", size="lg")

                    with gr.Column(scale=2):
                        exp_output = gr.Textbox(
                            label="Explanation",
                            lines=30,
                            interactive=False,
                            elem_classes="output-box"
                        )
                        with gr.Accordion("Raw JSON Output (for developers)", open=False):
                            exp_json = gr.Code(language="json", label="Structured JSON", lines=20)

                exp_btn.click(
                    fn=explain_concept,
                    inputs=[exp_concept, exp_level, exp_tone, exp_language,
                            exp_analogy, exp_example, exp_context],
                    outputs=[exp_output, exp_json]
                )

                gr.Examples(
                    examples=[
                        ["Backpropagation", "Beginner", "Friendly", "English", True, True,
                         "I'm learning neural networks for the first time"],
                        ["Gradient Descent", "Intermediate", "Strict", "Both", True, True, ""],
                        ["ओमको नियम (Ohm's Law)", "Beginner", "Friendly", "Nepali", True, True,
                         "कक्षा १० को विद्यार्थी"],
                    ],
                    inputs=[exp_concept, exp_level, exp_tone, exp_language,
                            exp_analogy, exp_example, exp_context],
                    label="📌 Try These Examples"
                )

            #TAB 3: AI TUTOR CHAT
            with gr.Tab("AI Tutor Chat", elem_classes="tab-content"):
                gr.Markdown("### Ask Follow-Up Questions — SmartStudy AI Remembers the Conversation")
                gr.Markdown(
                    "After generating a plan or explanation, ask follow-up questions here. "
                    "The AI remembers what you've discussed and builds on it."
                )

                chatbot = gr.Chatbot(
                    label="SmartStudy AI Tutor",
                    height=450,
                    bubble_full_width=False
                )

                with gr.Row():
                    chat_input = gr.Textbox(
                        placeholder="Ask a follow-up question... e.g. 'Can you explain Session 2 in more detail?'",
                        label="Your Message",
                        scale=4,
                        lines=1
                    )
                    chat_send = gr.Button("Send", variant="primary", scale=1)

                with gr.Row():
                    chat_clear = gr.Button("Clear Chat & Memory", variant="secondary")

                gr.Examples(
                    examples=[
                        ["Can you make Session 1 easier? I'm a complete beginner."],
                        ["Explain backpropagation using a cooking analogy instead."],
                        ["I only have 2 hours today instead of 4. Can you adjust?"],
                        ["What should I focus on if I only have 30 minutes?"],
                        ["Explain this in Nepali please."],
                    ],
                    inputs=chat_input,
                    label="📌 Example Follow-Up Questions"
                )

                chat_send.click(
                    fn=chat_followup,
                    inputs=[chat_input, chatbot],
                    outputs=[chatbot, chat_input]
                )
                chat_input.submit(
                    fn=chat_followup,
                    inputs=[chat_input, chatbot],
                    outputs=[chatbot, chat_input]
                )
                chat_clear.click(
                    fn=clear_chat,
                    outputs=[chatbot, chat_input]
                )

            # ── TAB 4: ABOUT ──────────────────────────────────────────────────
            with gr.Tab("About"):
                gr.Markdown("""