# Prompt Iteration Log — SmartStudy AI

> This file documents every version of the prompts used in SmartStudy AI,
> what changed between versions, why it changed, and what improved or failed.

---

## Study Planner Prompt Versions

---

### Version 1.0 — Initial Draft

**Date:** Week 1

**Prompt:**

```
You are a study planner. Create a study plan for the following:
Subject: {subjects}
Hours per day: {hours}
Goal: {goal}

Give me a day-by-day schedule.
```

**What happened:**

- Claude returned plain text paragraphs with no structure
- Could not be parsed programmatically at all
- Output varied wildly in format each time
- No JSON output → no structured data to display in the app

**What failed:**

- No instruction to return JSON
- No schema defined
- No constraints on length or format
- Output was inconsistent across runs

**Improvement needed:** Force JSON output with a defined schema.

---

### Version 1.1 — Added JSON Instruction

**Date:** Week 1

**Prompt:**

```
You are a study planner. Create a study plan and return it as JSON.

Subject: {subjects}
Hours per day: {hours}
Goal: {goal}

Return a JSON with keys: title, days, sessions.
```

**What happened:**

- Claude returned JSON sometimes, but often wrapped it in markdown (`json ... `)
- The schema was too vague — Claude invented its own key names
- "sessions" was sometimes a list, sometimes a nested dict
- Parsing failed ~40% of the time due to inconsistent structure

**What failed:**

- "return it as JSON" is not strong enough — Claude adds markdown fences
- Vague schema ("keys: title, days, sessions") gave Claude too much freedom
- No instruction to ONLY return JSON (Claude added explanation text before/after)

**Improvement needed:** Enforce exact schema, forbid markdown, forbid extra text.

---

### Version 1.2 — Strict Schema Enforcement

**Date:** Week 2

**Prompt:**

```
You are SmartStudy AI, an expert study planner.

IMPORTANT: You must return ONLY a valid JSON object. No markdown, no explanation, no extra text.

The JSON must follow this exact schema:
{
  "plan_title": "string",
  "total_days": number,
  "days": [
    {
      "day": number,
      "sessions": [
        {
          "topic": "string",
          "duration_minutes": number,
          "activity": "string"
        }
      ]
    }
  ]
}

Subject: {subjects}
Hours per day: {hours}
Goal: {goal}

Begin your response with { and end with }. Nothing else.
```

**What happened:**

- JSON parsing success rate improved to ~85%
- Schema was now consistent across runs
- But sessions didn't always add up to the right total hours
- No tone, language, or length options
- Motivation tips, break schedules, and resources were missing

**What failed:**

- Hours constraint not enforced in prompt → sessions sometimes exceeded daily hours
- No tone/language customization → all outputs felt the same
- Schema too minimal → missing useful fields like motivation_tip, break_schedule

**Improvement needed:** Add hours constraint, tone/language/length parameters, richer schema.

---

### Version 1.3 — Added Tone, Language, Length + Hours Constraint

**Date:** Week 2

**Prompt:**

```
You are SmartStudy AI — an expert academic coach and study planner.

Settings:
- Tone: {tone} (friendly / strict / motivational)
- Language: {language} (English / Nepali / Both)
- Plan length: {length} (short=1 day, medium=3 days, long=7 days)

STRICT RULES:
1. Return ONLY a valid JSON object. No markdown, no extra text.
2. Sessions per day must NOT exceed {hours} hours total.
3. Include breaks for plans over 3 hours.
4. If language is Nepali, write all fields in Nepali Devanagari.

Schema:
{
  "plan_title": "string",
  "total_days": number,
  "daily_hours": number,
  "days": [
    {
      "day": number,
      "date_label": "string",
      "focus_topic": "string",
      "sessions": [...],
      "motivation_tip": "string",
      "break_schedule": "string"
    }
  ],
  "overall_tips": ["string"]
}

Subject: {subjects}
Hours: {hours}
Goal: {goal}
Notes: {notes}

Respond ONLY with JSON. Start with { end with }.
```

**What happened:**

- Tone customization worked well — "strict" gave terse, commanding outputs
- Nepali language worked for simple content, struggled with technical terms
- Hours constraint was now mostly respected (still occasionally exceeded by 10-15 min)
- JSON parse success rate: ~93%
- "Both" language mode wasn't clearly defined — Claude guessed the format

**What failed:**

- "Both" language not precisely instructed → inconsistent bilingual format
- Time slots (e.g., "9:00 AM - 10:30 AM") were missing from sessions
- Resources field not included
- Warning field for edge cases (vague input, unrealistic hours) missing

**Improvement needed:** Define "Both" format precisely, add time_slot and resources to session schema, add warning field.

---

### Version 1.4 — Bilingual Format + Warning Field + Resources

**Date:** Week 3

**Prompt:**

```
You are SmartStudy AI — an expert academic coach and study planner.

STRICT RULES:
1. Return ONLY valid JSON. No markdown fences. No text outside JSON.
2. Sessions must total exactly the user's daily hours. Do not exceed them.
3. If language is Nepali: write all text in Devanagari script.
4. If language is Both: write each field as "English text | नेपाली अनुवाद".
5. If input is vague or unrealistic, note it in the "warning" field but still generate a plan.
6. Include time slots like "9:00 AM - 10:30 AM" for every session.

Schema:
{
  "plan_title": "string",
  "total_days": number,
  "daily_hours": number,
  "goal": "string",
  "tone": "string",
  "language": "string",
  "days": [
    {
      "day": number,
      "date_label": "string",
      "focus_topic": "string",
      "sessions": [
        {
          "session_number": number,
          "time_slot": "string",
          "topic": "string",
          "activity": "string",
          "duration_minutes": number,
          "resources": ["string"]
        }
      ],
      "daily_goal": "string",
      "motivation_tip": "string",
      "break_schedule": "string"
    }
  ],
  "overall_tips": ["string"],
  "warning": "string or null"
}

Subject: {subjects} | Hours: {hours} | Goal: {goal}
Tone: {tone} | Language: {language} | Length: {length}
Notes: {notes}

Start with { and end with }.
```

**What happened:**

- "Both" language mode now consistently produced "English | नेपाली" per field
- Warning field appeared correctly for edge cases (e.g., 12 hours/day → warning about burnout)
- Resources field populated well (e.g., ["Khan Academy", "GeeksForGeeks"])
- Time slots were now consistent and properly formatted
- JSON parse success rate: ~97%
- Remaining issue: sometimes Claude added a small preamble before the `{` when the prompt was very long

**What failed:**

- Very long prompts (7-day plans with many subjects) occasionally triggered Claude to add "Here is your plan:" before the JSON
- The "Both" format added significant token cost for 7-day plans

**Improvement needed:** Add "Begin with { and end with }. Do not add any sentence before the JSON." as a final reminder, and add the `json_start_reminder` line.

---

### Version 2.0 — Final Production Prompt (Current)

**Date:** Week 3

**Key changes from v1.4:**

1. Added explicit: "Respond with ONLY the JSON object. Begin with {{ and end with }}." as the very last line
2. Changed schema to use double braces `{{...}}` for Python `.format()` compatibility
3. Added `sublinear_tf` equivalent instruction: "do not add any preamble, greeting, or explanation"
4. Prompt moved to `prompts.py` for centralized management
5. All 6 parameters (subjects, hours, goal, tone, language, length, notes) now properly injected

**Result:**

- JSON parse success rate: ~99%
- All tone modes work correctly
- Bilingual output ("Both") works reliably
- Warning field catches edge cases
- Fully validated against schema in `utils.py`

**Remaining known issue:**

- Very technical Nepali terms (e.g., "backpropagation", "gradient descent") remain in English even when Nepali is selected — this is acceptable since no Nepali equivalent exists.

---

## Concept Explainer Prompt Versions

---

### Version 1.0 — Initial

```
Explain {concept} to a {level} student.
```

**Failed:** Unstructured text, no JSON, no analogy/example options, no language control.

---

### Version 1.1 — Added JSON + Basic Schema

```
Explain {concept} and return as JSON with: definition, explanation, example.
```

**Improved:** Basic JSON but schema too simple. No difficulty rating, no misconceptions, no study tips.

---

### Version 1.2 — Full Schema + Level/Language/Tone

Added complete schema with all fields. Added level-adaptive vocabulary instructions.
**Improved:** Depth control worked well. Beginner explanations were simpler. Advanced had technical depth.
**Failed:** Analogy and example were always included even when user set them to "no".

---

### Version 1.3 — Conditional Fields + Final (Current)

Added: `"Include analogy: {use_analogy}"` and `"Include real_world_example: {use_example}"` as explicit conditions.
Claude now respects these settings. `null` is returned for the field when disabled.

---

## Follow-Up Chat Prompt Versions

---

### Version 1.0

```
You are a tutor. Answer: {user_message}
```

**Failed:** No memory, no JSON, no context. Every message was independent.

---

### Version 1.1

Added history string. Returned plain text.
**Improved:** Context carried over. But no JSON structure — couldn't extract suggested_next_steps or session_summary reliably.

---

### Version 1.2 — Final (Current)

Full JSON schema with `response_type`, `message`, `suggested_next_steps`, `updated_topics_covered`, `session_summary`.
Added: "If student seems confused, detect it and adjust." Added off-topic redirect instruction.
**Result:** Structured, context-aware, helpful follow-up responses.

---
