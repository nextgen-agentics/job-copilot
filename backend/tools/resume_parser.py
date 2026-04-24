"""
resume_parser.py — LLM-powered Resume Parser with regex fallback
================================================================
Extracts text from a PDF with PyMuPDF, then uses Gemini to intelligently
parse the raw text into a structured profile.

If the Gemini call fails (e.g. 429 rate limit, network error), a fast
regex-based fallback runs instead — the upload always succeeds.

Model is set via set_model() — same model the user selected in the UI.
"""
import json
import os
import re
import time
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Module-level model — synced from agent via set_model()
_model_name: str = "gemini-2.0-flash"


def set_model(model_name: str) -> None:
    """Propagate the UI-selected model into this module."""
    global _model_name
    _model_name = model_name


# ── PDF text extraction ──────────────────────────────────────────────────────

def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract raw text from a PDF using PyMuPDF."""
    if not PYMUPDF_AVAILABLE:
        raise RuntimeError("PyMuPDF not installed. Run: pip install pymupdf")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    doc.close()
    return text.strip()


# ── LLM parser (primary) ─────────────────────────────────────────────────────

def _llm_parse(raw_text: str) -> dict:
    """
    Use Gemini LLM to extract a structured profile from raw resume text.
    Raises on failure so the caller can fall back to regex.
    """
    genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
    model = genai.GenerativeModel(_model_name)

    prompt = f"""You are a resume parser. Extract structured information from this resume text.

=== RAW RESUME TEXT ===
{raw_text[:4000]}

Respond with ONLY this exact JSON (no markdown, no extra text):
{{
  "full_name": "<candidate full name or null>",
  "email": "<email address or null>",
  "phone": "<phone number or null>",
  "location": "<city, country or null>",
  "linkedin_url": "<LinkedIn URL or null>",
  "github_url": "<GitHub URL or null>",
  "education": [
    {{
      "degree": "<degree name e.g. MSc Artificial Intelligence>",
      "institution": "<university name>",
      "year": "<graduation year or expected year or null>"
    }}
  ],
  "experience": [
    {{
      "title": "<job title>",
      "company": "<company name>",
      "duration": "<e.g. Jan 2023 – Present>",
      "summary": "<1-2 sentence summary of role>"
    }}
  ],
  "skills": ["<skill1>", "<skill2>"],
  "languages": ["<language1>"],
  "publications": ["<paper title or null>"],
  "summary": "<2-3 sentence professional summary of the candidate>",
  "strongest_areas": ["<top 3 domain strengths e.g. Computer Vision, PyTorch, Research>"]
}}

Rules:
- Extract ALL skills mentioned (programming languages, frameworks, tools, ML techniques)
- If a field is not found, use null or empty array []
- Do not invent information not present in the text"""

    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(temperature=0.1),
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
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError("LLM returned unparseable output")


# ── Regex fallback (fast, no API needed) ─────────────────────────────────────

def _regex_parse(raw_text: str) -> dict:
    """
    Fast rule-based fallback. Runs when Gemini is unavailable/rate-limited.
    Extracts the most critical fields so the agent still has useful context.
    """
    text_lower = raw_text.lower()

    # Email
    email_m = re.search(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", raw_text)
    email = email_m.group(0) if email_m else None

    # Phone
    phone_m = re.search(r"[\+]?[\d\s\-().]{7,18}", raw_text)
    phone = phone_m.group(0).strip() if phone_m else None

    # GitHub / LinkedIn
    gh_m = re.search(r"github\.com/([\w-]+)", raw_text, re.IGNORECASE)
    li_m = re.search(r"linkedin\.com/in/([\w-]+)", raw_text, re.IGNORECASE)
    github_url = f"https://github.com/{gh_m.group(1)}" if gh_m else None
    linkedin_url = f"https://linkedin.com/in/{li_m.group(1)}" if li_m else None

    # Skills — broad keyword list
    SKILL_KW = [
        "python", "pytorch", "tensorflow", "keras", "scikit-learn", "sklearn",
        "numpy", "pandas", "opencv", "huggingface", "transformers", "langchain",
        "llm", "gpt", "bert", "diffusion", "reinforcement learning",
        "computer vision", "nlp", "deep learning", "machine learning", "neural network",
        "javascript", "typescript", "react", "node", "sql", "postgresql", "mongodb",
        "docker", "kubernetes", "aws", "gcp", "azure", "git", "linux", "bash",
        "java", "c++", "c#", "rust", "go", "matlab", "r", "latex", "jupyter",
        "wandb", "mlflow", "fastapi", "flask", "django", "spark", "hadoop",
    ]
    skills = [s for s in SKILL_KW if s in text_lower]

    # Education
    edu_pattern = re.compile(
        r"(master|msc|m\.sc|bachelor|bsc|b\.sc|phd|ph\.d|m\.eng|meng|b\.eng)[^\n]{0,120}",
        re.IGNORECASE,
    )
    education_raw = list(set(edu_pattern.findall(raw_text)))[:4]
    education = [{"degree": e.strip(), "institution": None, "year": None} for e in education_raw]

    # Best-guess name: first non-empty line that looks like a name (2 capitalised words)
    name = None
    for line in raw_text.split("\n")[:8]:
        line = line.strip()
        if re.match(r"^[A-Z][a-z]+ [A-Z][a-z]+", line) and len(line) < 60:
            name = line
            break

    return {
        "full_name": name,
        "email": email,
        "phone": phone,
        "location": None,
        "linkedin_url": linkedin_url,
        "github_url": github_url,
        "education": education,
        "experience": [],
        "skills": skills,
        "languages": [],
        "publications": [],
        "summary": f"Resume extracted via fallback parser (LLM unavailable). {len(skills)} skills detected.",
        "strongest_areas": skills[:3] if skills else [],
        "_parsed_by": "regex_fallback",
    }


# ── Public entry point ────────────────────────────────────────────────────────

def parse_resume(pdf_bytes: bytes) -> dict:
    """
    Parse a PDF resume. Tries LLM first; falls back to regex on any API error.
    Called at upload time from main.py.

    Returns:
        dict with structured profile fields (never raises)
    """
    try:
        raw_text = _extract_pdf_text(pdf_bytes)
    except RuntimeError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"PDF extraction failed: {str(e)}"}

    if not raw_text:
        return {"error": "Could not extract text from PDF (may be image-based)"}

    # ── Try LLM parser ───────────────────────────────────────────────────────
    parsed = None
    llm_error = None

    try:
        parsed = _llm_parse(raw_text)
        parsed["_parsed_by"] = "llm"
    except Exception as e:
        llm_error = str(e)

    # ── Fall back to regex on ANY error (429, network, parse failure) ────────
    if parsed is None:
        parsed = _regex_parse(raw_text)
        parsed["_llm_error"] = llm_error  # surface the original error for debugging

    parsed["full_text"] = raw_text[:3000]   # keep raw text for agent context
    parsed["pages"] = raw_text.count("\f") + 1
    return parsed
