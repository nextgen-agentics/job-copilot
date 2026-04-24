"""
fit_scorer.py — LLM-powered Job Fit Analyzer
=============================================
Tool the agent calls. Internally calls Gemini (using the model selected in the UI)
to reason deeply about fit — far richer than any keyword heuristic.
Model name is passed in via the module-level setter set_model().
"""
import json
import os
import re
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Module-level model name — set by agent.py before calling the tool
_model_name: str = "gemini-2.0-flash"


def set_model(model_name: str) -> None:
    """Called by the agent loop to propagate the UI-selected model into this tool."""
    global _model_name
    _model_name = model_name


def analyze_job_fit(job_description: str, candidate_profile: str, preferences: str) -> str:
    """
    Use Gemini LLM to deeply analyze how well a candidate fits a job posting.
    Uses the same model the user selected in the UI (set via set_model()).

    Args:
        job_description: Full job posting text
        candidate_profile: Candidate's skills, education, experience summary
        preferences: Candidate's stated preferences (role, location, salary, visa)

    Returns:
        JSON with fit_score, verdict, breakdown, gaps, strengths, recommendation
    """
    try:
        genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
        model = genai.GenerativeModel(_model_name)

        prompt = f"""You are an expert career counselor analyzing a job application.

Analyze the fit between this candidate and job. Be honest — not every job is a great fit.

=== JOB DESCRIPTION ===
{job_description[:3000]}

=== CANDIDATE PROFILE ===
{candidate_profile[:2000]}

=== CANDIDATE PREFERENCES ===
{preferences[:600]}

Respond with ONLY this exact JSON (no markdown, no extra text):
{{
  "fit_score": <integer 0-100>,
  "verdict": "<one concise sentence summarizing the fit>",
  "fit_breakdown": {{
    "skills_match": <0-100>,
    "experience_match": <0-100>,
    "education_match": <0-100>,
    "preferences_match": <0-100>
  }},
  "matched_skills": ["<skill that matches>"],
  "skill_gaps": ["<required skill candidate lacks>"],
  "strengths": ["<specific strength for this role>"],
  "concerns": ["<specific concern or risk>"],
  "recommendation": "<apply_now | apply_with_gaps_noted | consider_carefully | skip>"
}}

Scoring guide:
- 90-100: Near-perfect match
- 75-89: Good match, worth applying with tailored cover letter
- 60-74: Moderate match, address gaps explicitly
- 40-59: Weak match, significant upskilling needed
- below 40: Poor fit"""

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.2),
        )

        text = response.text.strip()
        if text.startswith("```"):
            lines = text.split("\n")[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
            if text.startswith("json"):
                text = text[4:].strip()

        try:
            return json.dumps(json.loads(text))
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.dumps(json.loads(match.group()))
                except Exception:
                    pass
            return json.dumps({
                "fit_score": 70, "verdict": "Analysis complete (parse error).",
                "fit_breakdown": {"skills_match": 70, "experience_match": 70,
                                  "education_match": 70, "preferences_match": 70},
                "matched_skills": [], "skill_gaps": [], "strengths": [], "concerns": [],
                "recommendation": "apply_with_gaps_noted",
            })

    except Exception as e:
        return json.dumps({"error": f"LLM fit analysis failed: {str(e)}"})
