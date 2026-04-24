"""
Company Insights Tool — Wikipedia API + web data
Returns real company info for job seekers: overview, size, culture signals.
"""
import requests
import json
import re
from bs4 import BeautifulSoup


def get_company_insights(company_name: str) -> str:
    """
    Get real company information using Wikipedia's REST API and web data.

    Args:
        company_name: Name of the company (e.g. 'DeepMind', 'Zalando', 'ASML')

    Returns:
        JSON string with company overview, size, and relevant info for job seekers
    """
    try:
        # ── Wikipedia summary ──────────────────────────────────────────────────
        wiki_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + \
                   requests.utils.quote(company_name)
        wiki_resp = requests.get(wiki_url, timeout=8,
                                 headers={"User-Agent": "JobCopilot/1.0"})

        wiki_data = {}
        if wiki_resp.status_code == 200:
            w = wiki_resp.json()
            wiki_data = {
                "description": w.get("extract", "")[:600],
                "thumbnail": w.get("thumbnail", {}).get("source"),
                "wiki_url": w.get("content_urls", {}).get("desktop", {}).get("page"),
            }

        # ── DuckDuckGo Instant Answer API (no key needed) ────────────────────
        ddg_resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": f"{company_name} company", "format": "json", "no_redirect": 1},
            timeout=8,
            headers={"User-Agent": "JobCopilot/1.0"},
        )
        ddg_data = {}
        if ddg_resp.status_code == 200:
            ddg = ddg_resp.json()
            ddg_data = {
                "abstract": ddg.get("AbstractText", "")[:400],
                "website": ddg.get("AbstractURL", ""),
                "related_topics": [t.get("Text", "")[:100] for t in ddg.get("RelatedTopics", [])[:3]],
            }

        # ── Derive culture signals from description ───────────────────────────
        full_text = (wiki_data.get("description", "") + " " + ddg_data.get("abstract", "")).lower()
        culture_tags = []
        tag_keywords = {
            "research-driven": ["research", "laboratory", "lab", "academic"],
            "well-funded": ["billion", "ipo", "nasdaq", "funding", "valuation"],
            "open-source": ["open source", "open-source", "github"],
            "startup": ["startup", "founded 20", "founded 201", "founded 202"],
            "large-corp": ["fortune", "multinational", "global", "worldwide offices"],
            "ai-first": ["artificial intelligence", "machine learning", "deep learning"],
            "product-focused": ["product", "customer", "e-commerce", "saas"],
        }
        for tag, keywords in tag_keywords.items():
            if any(kw in full_text for kw in keywords):
                culture_tags.append(tag)

        result = {
            "company": company_name,
            "overview": wiki_data.get("description") or ddg_data.get("abstract") or "No data found",
            "website": ddg_data.get("website", ""),
            "culture_tags": culture_tags,
            "related_info": ddg_data.get("related_topics", []),
            "wikipedia_url": wiki_data.get("wiki_url", ""),
        }

        return json.dumps(result)

    except requests.RequestException as e:
        return json.dumps({"error": f"Network error: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Unexpected error: {str(e)}"})
