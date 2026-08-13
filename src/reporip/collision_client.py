from __future__ import annotations

from dataclasses import dataclass
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .domain_checker import normalize_repo_name


SEARCH_URL = "https://api.github.com/search/repositories"
USER_URL = "https://api.github.com/users"


class GitHubCollisionError(RuntimeError):
    """Raised when a GitHub collision check cannot be completed."""


@dataclass(frozen=True, slots=True)
class CollisionMatch:
    full_name: str
    stars: int
    created_at: str
    description: str
    html_url: str


@dataclass(frozen=True, slots=True)
class CollisionResult:
    search_term: str
    other_repositories: int
    exact_account: bool
    repository_matches: tuple[CollisionMatch, ...] = ()


def _headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "RepoRip/0.1",
    }
    token = token or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _read_json(request: Request, *, timeout: float) -> dict[str, object]:
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("message", "")
        except Exception:
            detail = ""
        message = f"GitHub returned HTTP {exc.code}"
        if detail:
            message += f": {detail}"
        raise GitHubCollisionError(message) from exc
    except URLError as exc:
        raise GitHubCollisionError(
            f"Could not reach GitHub: {exc.reason}"
        ) from exc
    except (json.JSONDecodeError, OSError) as exc:
        raise GitHubCollisionError(
            f"Invalid response from GitHub: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise GitHubCollisionError("GitHub returned an unexpected response.")
    return payload


def _exact_account_exists(
    term: str,
    *,
    headers: dict[str, str],
    timeout: float,
) -> bool:
    # GitHub logins are at most 39 characters.
    if len(term) > 39:
        return False

    request = Request(
        f"{USER_URL}/{quote(term)}",
        headers=headers,
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as exc:
        if exc.code == 404:
            return False
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("message", "")
        except Exception:
            detail = ""
        message = f"GitHub returned HTTP {exc.code}"
        if detail:
            message += f": {detail}"
        raise GitHubCollisionError(message) from exc
    except URLError as exc:
        raise GitHubCollisionError(
            f"Could not reach GitHub: {exc.reason}"
        ) from exc
    except (json.JSONDecodeError, OSError) as exc:
        raise GitHubCollisionError(
            f"Invalid response from GitHub: {exc}"
        ) from exc

    return (
        isinstance(payload, dict)
        and str(payload.get("login") or "").lower() == term.lower()
    )


def check_github_collision(
    search_term: str,
    *,
    current_full_name: str = "",
    token: str | None = None,
    timeout: float = 20.0,
) -> CollisionResult:
    term = normalize_repo_name(search_term)
    if not term:
        raise ValueError("search_term must contain letters or numbers")

    headers = _headers(token)
    query = f"{term} in:name"
    params = urlencode(
        {
            "q": query,
            "per_page": 100,
        }
    )
    request = Request(
        f"{SEARCH_URL}?{params}",
        headers=headers,
    )

    payload = _read_json(request, timeout=timeout)
    items = payload.get("items")
    if not isinstance(items, list):
        raise GitHubCollisionError(
            "GitHub response did not contain a repository list."
        )

    current = current_full_name.lower().strip()
    exact_repositories: list[CollisionMatch] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        repo_name = str(item.get("name") or "")
        full_name = str(item.get("full_name") or "")

        if normalize_repo_name(repo_name) != term:
            continue
        if current and full_name.lower() == current:
            continue

        exact_repositories.append(
            CollisionMatch(
                full_name=full_name or repo_name,
                stars=int(item.get("stargazers_count") or 0),
                created_at=str(item.get("created_at") or ""),
                description=str(item.get("description") or ""),
                html_url=str(item.get("html_url") or ""),
            )
        )

    exact_account = _exact_account_exists(
        term,
        headers=headers,
        timeout=timeout,
    )

    exact_repositories.sort(
        key=lambda match: (-match.stars, match.full_name.lower())
    )

    return CollisionResult(
        search_term=term,
        other_repositories=len(exact_repositories),
        exact_account=exact_account,
        repository_matches=tuple(exact_repositories),
    )
