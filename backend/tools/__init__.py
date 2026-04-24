"""
Tools registry — all tools the agent can call.
"""
from .job_search import search_jobs
from .github_parser import fetch_github_repos
from .company_insights import get_company_insights
from .salary_data import get_salary_benchmark
from .visa_checker import check_visa_sponsorship
from .fit_scorer import analyze_job_fit, set_model as set_fit_model
from .resume_parser import set_model as set_resume_model

TOOLS = {
    "search_jobs": search_jobs,
    "fetch_github_repos": fetch_github_repos,
    "get_company_insights": get_company_insights,
    "get_salary_benchmark": get_salary_benchmark,
    "check_visa_sponsorship": check_visa_sponsorship,
    "analyze_job_fit": analyze_job_fit,
}


def sync_model(model_name: str) -> None:
    """Propagate the UI-selected model to all LLM-powered tools."""
    set_fit_model(model_name)
    set_resume_model(model_name)


__all__ = ["TOOLS", "sync_model"]
