from __future__ import annotations
import base64
import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from .models import Repository

class BusinessEvidenceError(RuntimeError):
    pass

@dataclass(frozen=True, slots=True)
class RepositoryBusinessEvidence:
    readme_excerpt: str = ""
    topics: tuple[str, ...] = ()
    homepage: str = ""
    license_name: str = ""
    forks: int = 0
    open_issues: int = 0

def _headers(token=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "RepoRip/0.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = token or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def _json_request(url, *, token=None, timeout=8.0):
    request = Request(url, headers=_headers(token))
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise BusinessEvidenceError(f"GitHub returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise BusinessEvidenceError(f"Could not reach GitHub: {exc.reason}") from exc
    except (json.JSONDecodeError, OSError) as exc:
        raise BusinessEvidenceError(f"Invalid GitHub response: {exc}") from exc
    if not isinstance(payload, dict):
        raise BusinessEvidenceError("GitHub response was not an object.")
    return payload

def fetch_repository_business_evidence(repo: Repository, *, token=None, timeout=8.0):
    if not repo.full_name or "/" not in repo.full_name:
        raise ValueError("Repository full_name is required.")
    base = f"https://api.github.com/repos/{repo.full_name}"
    metadata = _json_request(base, token=token, timeout=timeout)

    readme_excerpt = ""
    try:
        readme = _json_request(base + "/readme", token=token, timeout=timeout)
        encoded = readme.get("content")
        if isinstance(encoded, str):
            raw = base64.b64decode(encoded.encode("ascii"), validate=False)
            readme_excerpt = raw.decode("utf-8", errors="replace")[:12000]
    except BusinessEvidenceError as exc:
        if "HTTP 404" not in str(exc):
            raise

    raw_topics = metadata.get("topics", [])
    topics = tuple(
        str(item).strip()
        for item in raw_topics
        if isinstance(item, str) and item.strip()
    )

    license_info = metadata.get("license")
    license_name = ""
    if isinstance(license_info, dict):
        license_name = str(
            license_info.get("spdx_id")
            or license_info.get("name")
            or ""
        )

    return RepositoryBusinessEvidence(
        readme_excerpt=readme_excerpt,
        topics=topics,
        homepage=str(metadata.get("homepage") or ""),
        license_name=license_name,
        forks=int(metadata.get("forks_count") or 0),
        open_issues=int(metadata.get("open_issues_count") or 0),
    )
