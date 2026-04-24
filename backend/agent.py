"""
agent.py — JobCopilot AI Agent Loop
=====================================
Follows the reference.py pattern:
  Query → LLM → Tool Call → Tool Result → Query → LLM → ... → Final Answer
  Each Query accumulates ALL past messages.

SSE events emitted (all visible in the UI reasoning chain):
  {type: "llm_call",    model, iteration, prompt_tokens}
  {type: "llm_output",  raw, iteration}
  {type: "tool_call",   tool, args, iteration}
  {type: "tool_result", tool, result, iteration}
  {type: "answer",      content, dashboard, iterations}
  {type: "retry",       content}
  {type: "error",       content}
"""
import json
import re
import inspect
import os
import google.generativeai as genai
from dotenv import load_dotenv
from tools import TOOLS, sync_model

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# System Prompt
# ──────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are JobCopilot AI — an intelligent career assistant that helps people find and evaluate tech jobs.

The candidate's resume, GitHub summary, and preferences are already provided in the User message below.
Do NOT try to re-parse or re-fetch what is already given — use it directly.

You have access to the following tools:

1. search_jobs(role: str, location: str, experience_level: str) -> str
   Search for real job openings via Arbeitnow (on-site/hybrid) + Remotive (remote tech). Free, no key needed.
   Examples: search_jobs("ML Engineer", "Berlin", "entry"), search_jobs("Research Scientist", "London", "mid")

2. fetch_github_repos(github_url: str) -> str
   Fetch LIVE GitHub profile and project details when the candidate provides a GitHub URL.
   Example: fetch_github_repos("https://github.com/username")

3. get_company_insights(company_name: str) -> str
   Get company overview, culture signals, tech stack, and hiring context.
   Examples: get_company_insights("DeepMind"), get_company_insights("Spotify")

4. get_salary_benchmark(role: str, location: str) -> str
   Get real salary data — first from live job listings, then curated benchmarks.
   Examples: get_salary_benchmark("Data Scientist", "Amsterdam"), get_salary_benchmark("SWE", "London")

5. check_visa_sponsorship(company: str, country: str) -> str
   Check if a company sponsors work visas for a given country.
   Examples: check_visa_sponsorship("Google", "uk"), check_visa_sponsorship("ASML", "netherlands")

6. analyze_job_fit(job_description: str, candidate_profile: str, preferences: str) -> str
   Uses an LLM internally to deeply analyze fit. ALWAYS call this for job analysis — never score fit yourself.
   Returns: fit_score 0-100, verdict, per-dimension breakdown, matched skills, gaps, strengths, concerns, recommendation.
   Example: analyze_job_fit("Senior ML Engineer role focused on CV...", "MSc AI, PyTorch, 2 years CV experience...", "Remote or London, research role, £70k+")

You must respond in ONE of these two JSON formats ONLY:

If you need to use a tool:
{"tool_name": "<name>", "tool_arguments": {"<arg>": "<value>"}}

If you have the final answer (after gathering all needed tool data):
{"answer": "<summary>", "dashboard": {"fit_score": <0-100>, "verdict": "<one line>", "fit_breakdown": {"skills_match": <0-100>, "experience_match": <0-100>, "education_match": <0-100>, "preferences_match": <0-100>}, "salary": {"min": <int>, "max": <int>, "median": <int>, "currency": "<str>"}, "company_insights": {"description": "<str>", "culture_tags": ["<str>"], "website": "<str>"}, "visa_info": {"sponsors_visa": <bool>, "visa_type": "<str>", "language_requirements": "<str>"}, "resume_bullets": ["<bullet1>", "<bullet2>", "<bullet3>", "<bullet4>", "<bullet5>"], "cover_letter_points": ["<point1>", "<point2>", "<point3>", "<point4>"], "interview_questions": ["<q1>", "<q2>", "<q3>", "<q4>", "<q5>"]}}

RULES:
- ONLY output JSON. No markdown fences, no extra text.
- For job analysis: call tools in this order: analyze_job_fit → get_company_insights → get_salary_benchmark → check_visa_sponsorship.
- USE analyze_job_fit TOOL — never compute fit score yourself. Copy fit_score and fit_breakdown from tool result into dashboard.
- resume_bullets: Rewrite 5 of the candidate's bullet points to match this job's keywords and language.
- cover_letter_points: 4 tailored narrative points for this company and role.
- interview_questions: 5 smart "reverse interview" questions the candidate should ask.
- Each iteration keeps ALL past messages. Never repeat a tool call.
"""


# ──────────────────────────────────────────────────────────────────────────────
# LLM Call
# ──────────────────────────────────────────────────────────────────────────────
def call_llm(prompt: str, model_name: str = "gemini-2.0-flash") -> str:
    """Send accumulated prompt to Gemini and return raw text response."""
    genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(temperature=0.1),
    )
    return response.text


# ──────────────────────────────────────────────────────────────────────────────
# Response Parser (reference.py pattern)
# ──────────────────────────────────────────────────────────────────────────────
def parse_llm_response(text: str) -> dict:
    """Parse LLM JSON response, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Could not parse LLM response: {text[:300]}")


def extract_tool_args(parsed: dict, tool_name: str) -> dict:
    """Forgiving argument extractor — handles LLM key variations (from reference.py)."""
    CANDIDATE_KEYS = (
        "tool_arguments", "tool_args", "arguments", "args",
        "parameters", "params", "input", "inputs",
    )
    raw = None
    for key in CANDIDATE_KEYS:
        if key in parsed:
            raw = parsed[key]
            break
    if raw is None:
        extras = {k: v for k, v in parsed.items()
                  if k not in ("tool_name", "answer", "dashboard", "name")}
        if extras:
            raw = extras
    if isinstance(raw, dict):
        return raw
    if raw is not None and tool_name in TOOLS:
        sig = inspect.signature(TOOLS[tool_name])
        params = [p for p in sig.parameters if p != "self"]
        if len(params) == 1:
            return {params[0]: raw}
    return {}


# ──────────────────────────────────────────────────────────────────────────────
# Agent Loop — yields SSE event dicts (all visible in UI reasoning chain)
# ──────────────────────────────────────────────────────────────────────────────
def run_agent(query: str, profile: dict, page_context: str,
              model_name: str = "gemini-2.0-flash"):
    """
    Multi-step agent loop (reference.py pattern).
    Yields SSE events for EVERY step: LLM call, LLM raw output, tool call, tool result, final answer.

    Query → LLM → Tool → Result → Query → LLM → Tool → Result → Query → Answer
    Each Query accumulates ALL past messages.
    """
    # ── Sync model to LLM-powered tools ──────────────────────────────────────
    sync_model(model_name)

    # ── Build initial user message from profile + page context ────────────────
    user_parts = [f"User Query: {query}"]

    if page_context:
        user_parts.append(
            f"\n\nCurrent Job Posting (auto-extracted from browser tab):\n{page_context[:3000]}"
        )

    if profile.get("resume"):
        resume = profile["resume"]
        # Support both LLM-parsed (new) and legacy field names
        skills = resume.get("skills", [])
        education = resume.get("education", resume.get("education_mentions", []))
        edu_str = ""
        if education and isinstance(education[0], dict):
            edu_str = "; ".join(
                f"{e.get('degree', '')} @ {e.get('institution', '')}" for e in education[:3]
            )
        else:
            edu_str = ", ".join(str(e) for e in education[:3])

        user_parts.append(
            f"\n\nCandidate Profile:\n"
            f"Skills: {', '.join(skills[:30])}\n"
            f"Education: {edu_str}\n"
            f"Summary: {resume.get('summary', resume.get('full_text', ''))[:600]}"
        )

    if profile.get("github"):
        gh = profile["github"]
        user_parts.append(
            f"\n\nGitHub: {gh.get('profile', {}).get('username', '')} — "
            f"Top languages: {list(gh.get('top_languages', {}).keys())[:5]} — "
            f"ML/AI repos: {gh.get('ml_ai_projects', [])[:5]}"
        )

    if profile.get("preferences"):
        user_parts.append(f"\n\nJob Preferences: {profile['preferences']}")

    user_message = "\n".join(user_parts)

    # ── Message history (reference.py: accumulate every turn) ─────────────────
    messages = [
        {"role": "system",    "content": SYSTEM_PROMPT},
        {"role": "user",      "content": user_message},
    ]

    max_iterations = 10

    for iteration in range(max_iterations):

        # ── Build flat prompt from ALL accumulated messages ───────────────────
        prompt = ""
        for msg in messages:
            if msg["role"] == "system":
                prompt += msg["content"] + "\n\n"
            elif msg["role"] == "user":
                prompt += f"User: {msg['content']}\n\n"
            elif msg["role"] == "assistant":
                prompt += f"Assistant: {msg['content']}\n\n"
            elif msg["role"] == "tool":
                prompt += f"Tool Result: {msg['content']}\n\n"

        # ── Emit: LLM call event ──────────────────────────────────────────────
        yield {
            "type": "llm_call",
            "model": model_name,
            "iteration": iteration + 1,
            "prompt_preview": prompt[-600:].strip(),  # last 600 chars for display
        }

        # ── Call LLM ─────────────────────────────────────────────────────────
        try:
            response_text = call_llm(prompt, model_name)
        except Exception as e:
            yield {"type": "error", "content": f"LLM error: {str(e)}"}
            return

        # ── Emit: raw LLM output ──────────────────────────────────────────────
        yield {
            "type": "llm_output",
            "raw": response_text[:1200],   # cap for SSE payload size
            "iteration": iteration + 1,
        }

        # ── Parse response ────────────────────────────────────────────────────
        try:
            parsed = parse_llm_response(response_text)
        except ValueError:
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user",
                             "content": "Please respond with valid JSON only. No markdown, no extra text."})
            yield {"type": "retry",
                   "content": f"Iteration {iteration + 1}: response wasn't valid JSON — retrying."}
            continue

        # ── Final answer ──────────────────────────────────────────────────────
        if "answer" in parsed:
            yield {
                "type": "answer",
                "content": parsed["answer"],
                "dashboard": parsed.get("dashboard", {}),
                "iterations": iteration + 1,
            }
            return

        # ── Tool call ─────────────────────────────────────────────────────────
        if "tool_name" in parsed:
            tool_name = parsed["tool_name"]
            tool_args = extract_tool_args(parsed, tool_name)

            yield {
                "type": "tool_call",
                "tool": tool_name,
                "args": tool_args,
                "iteration": iteration + 1,
            }

            if tool_name not in TOOLS:
                err = json.dumps({"error": f"Unknown tool '{tool_name}'. Available: {list(TOOLS.keys())}"})
                yield {"type": "tool_result", "tool": tool_name,
                       "result": {"error": f"Unknown tool: {tool_name}"}, "iteration": iteration + 1}
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "tool", "content": err})
                continue

            try:
                tool_result_str = TOOLS[tool_name](**tool_args)
            except TypeError as e:
                err = json.dumps({"error": f"Bad arguments for {tool_name}: {e}"})
                yield {"type": "tool_result", "tool": tool_name,
                       "result": {"error": str(e)}, "iteration": iteration + 1}
                messages.append({"role": "assistant", "content": response_text})
                messages.append({"role": "tool", "content": err})
                continue

            try:
                tool_result_obj = json.loads(tool_result_str)
            except Exception:
                tool_result_obj = {"raw": tool_result_str}

            yield {
                "type": "tool_result",
                "tool": tool_name,
                "result": tool_result_obj,
                "iteration": iteration + 1,
            }

            # ── Accumulate ALL history (core reference.py requirement) ────────
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "tool",      "content": tool_result_str})
            continue

        # Unexpected format — nudge
        messages.append({"role": "assistant", "content": response_text})
        messages.append({"role": "user",
                         "content": "Please respond with valid JSON in the required format."})

    yield {"type": "error", "content": "Max iterations reached. Could not complete analysis."}
