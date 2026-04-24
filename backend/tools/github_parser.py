"""
GitHub Parser Tool — GitHub REST API
Fetches a candidate's public repositories and extracts project highlights.
No authentication required for public repos (60 req/hour unauthenticated).
"""
import requests
import json
import re


def fetch_github_repos(github_url: str) -> str:
    """
    Fetch GitHub profile and top repositories for a candidate.

    Args:
        github_url: GitHub profile URL (e.g. 'https://github.com/username')

    Returns:
        JSON string with profile info and top repos
    """
    try:
        # Extract username from URL
        username = github_url.strip().rstrip("/").split("/")[-1]
        if not username or username.startswith("http"):
            return json.dumps({"error": "Invalid GitHub URL. Expected: https://github.com/username"})

        headers = {"Accept": "application/vnd.github.v3+json"}

        # Fetch user profile
        user_resp = requests.get(
            f"https://api.github.com/users/{username}",
            headers=headers, timeout=10,
        )
        if user_resp.status_code == 404:
            return json.dumps({"error": f"GitHub user '{username}' not found"})
        if user_resp.status_code != 200:
            return json.dumps({"error": f"GitHub API error: {user_resp.status_code}"})

        user = user_resp.json()
        profile = {
            "username": username,
            "name": user.get("name"),
            "bio": user.get("bio"),
            "public_repos": user.get("public_repos", 0),
            "followers": user.get("followers", 0),
            "location": user.get("location"),
            "blog": user.get("blog"),
        }

        # Fetch top repos (non-forks, sorted by stars)
        repos_resp = requests.get(
            f"https://api.github.com/users/{username}/repos",
            params={"sort": "updated", "per_page": 20, "type": "owner"},
            headers=headers, timeout=10,
        )
        repos = repos_resp.json() if repos_resp.status_code == 200 else []

        # Filter and rank repos
        own_repos = [r for r in repos if not r.get("fork", True)]
        own_repos.sort(key=lambda r: r.get("stargazers_count", 0), reverse=True)

        highlights = []
        languages = {}
        for repo in own_repos[:6]:
            lang = repo.get("language")
            if lang:
                languages[lang] = languages.get(lang, 0) + 1

            highlights.append({
                "name": repo["name"],
                "description": repo.get("description"),
                "language": lang,
                "stars": repo.get("stargazers_count", 0),
                "topics": repo.get("topics", []),
                "url": repo.get("html_url"),
                "updated": repo.get("updated_at", "")[:10],
            })

        # Infer skills from repos
        ml_keywords = ["pytorch", "tensorflow", "keras", "sklearn", "ml", "deep-learning",
                        "neural", "cv", "nlp", "transformers", "llm", "diffusion"]
        ml_repos = [r for r in highlights if any(
            kw in (r.get("name", "") + " ".join(r.get("topics", []))).lower()
            for kw in ml_keywords
        )]

        return json.dumps({
            "profile": profile,
            "top_languages": languages,
            "repositories": highlights,
            "ml_ai_repos_count": len(ml_repos),
            "ml_ai_projects": [r["name"] for r in ml_repos],
        })

    except requests.RequestException as e:
        return json.dumps({"error": f"Network error: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Unexpected error: {str(e)}"})
