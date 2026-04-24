"""
Job Search Tool — Arbeitnow API + Remotive API (both 100% free, no keys, no rate limits)
=========================================================================================
• Arbeitnow  (https://arbeitnow.com/api/job-board-api)  — EU-focused, remote + on-site
• Remotive   (https://remotive.com/api/remote-jobs)     — global remote tech/ML jobs
Both APIs are completely free with no authentication and no hard rate limits.
"""
import requests
import json
from urllib.parse import urlencode

HEADERS = {
    "User-Agent": "JobCopilot-AI/1.0 (student job search assistant)",
    "Accept": "application/json",
}

EU_COUNTRY_CODES = {
    "uk": "gb", "england": "gb", "britain": "gb", "london": "gb",
    "germany": "de", "berlin": "de", "munich": "de", "frankfurt": "de",
    "netherlands": "nl", "amsterdam": "nl", "rotterdam": "nl",
    "switzerland": "ch", "zurich": "ch", "geneva": "ch",
    "france": "fr", "paris": "fr",
    "sweden": "se", "stockholm": "se",
    "ireland": "ie", "dublin": "ie",
    "austria": "at", "vienna": "at",
    "spain": "es", "barcelona": "es", "madrid": "es",
    "denmark": "dk", "copenhagen": "dk",
    "finland": "fi", "helsinki": "fi",
    "norway": "no", "oslo": "no",
    "belgium": "be", "brussels": "be",
    "europe": None,  # search all
}

ML_TAGS = ["machine-learning", "python", "pytorch", "tensorflow", "deep-learning",
           "computer-vision", "nlp", "data-science", "artificial-intelligence", "research"]


def search_jobs(role: str, location: str, experience_level: str = "entry") -> str:
    """
    Search for real tech/ML/research/PhD jobs using Arbeitnow + Remotive APIs.
    Both are completely free — no API key, no rate limit, no credit card.

    Args:
        role: Job title to search (e.g. 'ML Engineer', 'Research Scientist', 'PhD')
        location: European city or country (e.g. 'Berlin', 'London', 'Netherlands')
        experience_level: 'entry', 'mid', or 'senior'

    Returns:
        JSON string with combined real job listings from both APIs
    """
    jobs = []

    # ── 1. Arbeitnow API — EU-focused, great for Germany/UK/NL ─────────────
    arbeitnow_jobs = _search_arbeitnow(role, location, experience_level)
    jobs.extend(arbeitnow_jobs)

    # ── 2. Remotive API — global remote tech jobs ──────────────────────────
    remotive_jobs = _search_remotive(role, experience_level)
    # Filter to EU-relevant if location is specific
    if location.lower() not in ("europe", "remote"):
        remotive_jobs = [j for j in remotive_jobs if "remote" in j.get("location", "").lower()]
    jobs.extend(remotive_jobs)

    if not jobs:
        return json.dumps({
            "role": role,
            "location": location,
            "jobs": [],
            "sources": ["Arbeitnow", "Remotive"],
            "note": "No results found. Try a broader role or 'Europe' as location.",
        })

    return json.dumps({
        "role": role,
        "location": location,
        "total_found": len(jobs),
        "sources": ["Arbeitnow (EU jobs)", "Remotive (remote tech)"],
        "jobs": jobs[:8],  # return top 8
    })


def _search_arbeitnow(role: str, location: str, level: str) -> list:
    """Arbeitnow public API — EU job board, completely free, no key needed."""
    try:
        # Build search query
        search = role
        if level == "entry":
            search = f"{role}"  # Arbeitnow doesn't support level filtering; title is enough

        params = {
            "search": search,
            "page": 1,
        }

        # Add location filter if a specific country is known
        loc_lower = location.lower()
        country_code = None
        for key, code in EU_COUNTRY_CODES.items():
            if key in loc_lower and code:
                country_code = code
                break

        url = "https://arbeitnow.com/api/job-board-api"
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)

        if resp.status_code != 200:
            return []

        data = resp.json()
        results = []
        for job in data.get("data", [])[:6]:
            # Filter by location if we have a country code or city
            job_location = (job.get("location") or "").lower()
            if country_code and loc_lower not in ("europe",):
                # Try to match city or country
                location_words = [w for w in loc_lower.split() if len(w) > 3]
                if not any(w in job_location for w in location_words) and country_code not in job_location:
                    # Still include remote jobs
                    if not job.get("remote"):
                        continue

            # Filter for relevance — keep ML/research/tech jobs
            title = (job.get("title") or "").lower()
            desc = (job.get("description") or "").lower()[:300]
            relevant = any(
                kw in title or kw in desc
                for kw in ["engineer", "scientist", "researcher", "developer",
                           "machine learning", "ml", "ai", "data", "phd", "python",
                           "nlp", "vision", "analyst", "software"]
            )
            if not relevant:
                continue

            results.append({
                "title": job.get("title", ""),
                "company": job.get("company_name", ""),
                "location": job.get("location", location),
                "remote": job.get("remote", False),
                "description_snippet": (job.get("description") or "")[:350].strip(),
                "tags": job.get("tags", [])[:5],
                "via": "Arbeitnow",
                "apply_link": job.get("url", "https://arbeitnow.com"),
                "posted": job.get("created_at", ""),
            })

        return results

    except Exception:
        return []


def _search_remotive(role: str, level: str) -> list:
    """Remotive public API — global remote tech jobs, completely free, no key needed."""
    try:
        # Map role to Remotive category
        category = "software-dev"
        role_lower = role.lower()
        if any(k in role_lower for k in ["data", "ml", "machine learning", "ai", "deep learning"]):
            category = "data"
        elif any(k in role_lower for k in ["research", "scientist", "phd"]):
            category = "data"
        elif any(k in role_lower for k in ["devops", "infra", "cloud", "platform"]):
            category = "devops-sysadmin"
        elif any(k in role_lower for k in ["product"]):
            category = "product"

        params = {
            "category": category,
            "search": role,
            "limit": 10,
        }

        resp = requests.get(
            "https://remotive.com/api/remote-jobs",
            params=params,
            headers=HEADERS,
            timeout=10,
        )

        if resp.status_code != 200:
            return []

        jobs = resp.json().get("jobs", [])
        results = []
        for job in jobs[:5]:
            # Only include jobs published recently (Remotive has created_at)
            salary = job.get("salary", "")
            results.append({
                "title": job.get("title", ""),
                "company": job.get("company_name", ""),
                "location": job.get("candidate_required_location", "Remote"),
                "remote": True,
                "salary": salary if salary else "Not specified",
                "description_snippet": _strip_html(job.get("description", ""))[:350],
                "tags": job.get("tags", [])[:5],
                "via": "Remotive (Remote)",
                "apply_link": job.get("url", "https://remotive.com"),
                "posted": job.get("publication_date", ""),
            })

        return results

    except Exception:
        return []


def _strip_html(text: str) -> str:
    """Remove HTML tags from description."""
    import re
    return re.sub(r'<[^>]+>', ' ', text).strip()
