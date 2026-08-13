from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Repository


API_URL = "https://api.github.com/search/repositories"


class GitHubSearchError(RuntimeError):
    """Raised when a GitHub repository search cannot be completed."""


def build_search_query(
    *,
    days: int,
    min_stars: int,
    language: str = "",
    category: str = "",
    now: datetime | None = None,
) -> str:
    if days < 1:
        raise ValueError("days must be at least 1")
    if min_stars < 0:
        raise ValueError("min_stars cannot be negative")

    now = now or datetime.now(timezone.utc)
    created_after = (now - timedelta(days=days)).date().isoformat()

    parts: list[str] = []

    category = category.strip()
    if category:
        parts.append(category)

    parts.extend(
        [f"created:>={created_after}", f"stars:>={min_stars}"]
    )
    language = language.strip()
    if language:
        parts.append(f"language:{language}")

    return " ".join(parts)


def _parse_repository(item: dict[str, Any]) -> Repository:
    return Repository(
        name=str(item.get("name") or ""),
        full_name=str(item.get("full_name") or ""),
        stars=int(item.get("stargazers_count") or 0),
        created_at=str(item.get("created_at") or ""),
        language=str(item.get("language") or ""),
        description=str(item.get("description") or ""),
        html_url=str(item.get("html_url") or ""),
    )


def search_repositories(
    *,
    days: int = 7,
    min_stars: int = 10,
    language: str = "",
    category: str = "",
    max_results: int = 50,
    token: str | None = None,
    timeout: float = 20.0,
) -> list[Repository]:
    if not 1 <= max_results <= 300:
        raise ValueError("max_results must be between 1 and 300")

    query = build_search_query(
        days=days,
        min_stars=min_stars,
        language=language,
        category=category,
    )

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "RepoRip/0.1",
    }

    token = token or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    repositories: list[Repository] = []
    seen: set[str] = set()
    page = 1

    while len(repositories) < max_results:
        remaining = max_results - len(repositories)
        per_page = min(100, remaining)

        params = urlencode(
            {
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": per_page,
                "page": page,
            }
        )
        request = Request(f"{API_URL}?{params}", headers=headers)

        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8")).get(
                    "message",
                    "",
                )
            except Exception:
                detail = ""
            message = f"GitHub returned HTTP {exc.code}"
            if detail:
                message += f": {detail}"
            raise GitHubSearchError(message) from exc
        except URLError as exc:
            raise GitHubSearchError(
                f"Could not reach GitHub: {exc.reason}"
            ) from exc
        except (json.JSONDecodeError, OSError) as exc:
            raise GitHubSearchError(
                f"Invalid response from GitHub: {exc}"
            ) from exc

        items = payload.get("items")
        if not isinstance(items, list):
            raise GitHubSearchError(
                "GitHub response did not contain a repository list."
            )

        for item in items:
            if not isinstance(item, dict):
                continue

            repo = _parse_repository(item)
            identity = repo.full_name or repo.html_url or repo.name
            if identity in seen:
                continue

            seen.add(identity)
            repositories.append(repo)

            if len(repositories) >= max_results:
                break

        if len(items) < per_page:
            break

        page += 1

    return repositories
