from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re

from .models import Repository

NOISE_WORDS = {
    "agent", "agents", "api", "app", "apps", "assistant",
    "boilerplate", "bot", "cli", "client", "clone", "code", "collection",
    "demo", "example", "explorer", "fork", "framework", "github",
    "plugin", "preview", "repo", "sample", "sdk", "server", "skill",
    "skills", "starter", "template", "test", "tool", "tools", "wrapper",
}

TECH_FRAGMENTS = ("comfyui", "minimax", "claude", "codex", "deepseek")

# Compact vocabulary for detecting descriptive/product-like phrases. These are
# not banned words; they only add penalties when they make a candidate read
# more like a literal project description than a distinctive brand.
DESCRIPTIVE_FRAGMENTS = {
    "app", "apps", "audio", "book", "chat", "cloud", "code", "data",
    "file", "for", "free", "game", "hub", "lab", "love", "map",
    "media", "music", "my", "online", "player", "project", "repo",
    "search", "studio", "tool", "video", "web",
}

DESCRIPTIVE_SUFFIXES = (
    "app", "bot", "chat", "hub", "lab", "player", "studio", "tool", "web",
)

# Signals that a repository is primarily a derivative, compatibility layer,
# integration, port, or reproduction of another product/project.
DERIVATIVE_TERMS = {
    "clone",
    "compatibility",
    "extension",
    "fork",
    "frontend",
    "integration",
    "mirror",
    "mod",
    "plugin",
    "port",
    "reimplementation",
    "replacement",
    "skin",
    "theme",
    "unofficial",
    "wrapper",
}

# Established ecosystem/product markers reduce independence as a new brand.
ESTABLISHED_NAME_MARKERS = {
    "android": 10, "apple": 10, "arxiv": 14, "chatgpt": 16,
    "chrome": 12, "claude": 16, "discord": 14, "docker": 12,
    "facebook": 16, "github": 16, "gitlab": 16, "google": 16,
    "instagram": 16, "linux": 10, "microsoft": 16, "netflix": 16,
    "openai": 16, "reddit": 14, "spotify": 16, "telegram": 14,
    "tiktok": 16, "twitter": 16, "wechat": 18, "whatsapp": 16,
    "windows": 12, "youtube": 16,
}

# Common descriptive building blocks. Multiple hits suggest a project label
# rather than a distinctive standalone brand.
DESCRIPTIVE_NAME_PARTS = {
    "audio", "book", "browser", "code", "data", "diff", "feed", "file",
    "flow", "form", "human", "image", "mail", "motion", "music", "note",
    "oil", "phone", "photo", "search", "text", "video", "voice", "web",
    "word", "write", "writing", "harness",
}


GENERIC_PROJECT_MARKERS = {
    "api": 4, "bot": 5, "cli": 4, "demo": 5, "example": 7,
    "plugin": 6, "sdk": 5, "server": 4, "template": 8,
    "tool": 4, "wrapper": 7,
}

DERIVATIVE_PHRASES = (
    "alternative to",
    "compatible with",
    "drop-in replacement",
    "drop in replacement",
    "fork of",
    "frontend for",
    "interface for",
    "plugin for",
    "port of",
    "reimplementation of",
    "replacement for",
    "theme for",
    "wrapper for",
)
VOWELS = set("aeiouy")


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    candidate_score: int
    total: int
    name_quality: int
    brandability: int
    momentum: int
    com_bonus: int
    penalties: int


def _repo_tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", name.lower()) if t]


def _age_days(created_at: str, *, now: datetime) -> float:
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return 30.0
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return max(1 / 24, (now - created).total_seconds() / 86400)


def _longest_consonant_run(term: str) -> int:
    longest = 0
    current = 0
    for char in term:
        if char.isalpha() and char not in VOWELS:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _descriptive_phrase_penalty(term: str, tokens: list[str]) -> int:
    penalty = 0

    # Explicit GitHub separators give us useful word boundaries.
    descriptor_hits = sum(
        1 for token in tokens
        if token in DESCRIPTIVE_FRAGMENTS
    )
    if descriptor_hits >= 2:
        penalty += min(14, descriptor_hits * 4)
    elif descriptor_hits == 1 and len(tokens) >= 3:
        penalty += 3

    # Repo names are often already concatenated, so also look for a small set
    # of strong descriptive fragments inside the normalized domain candidate.
    embedded_hits = {
        fragment for fragment in DESCRIPTIVE_FRAGMENTS
        if len(fragment) >= 3 and fragment in term
    }
    if len(embedded_hits) >= 3:
        penalty += 12
    elif len(embedded_hits) == 2:
        penalty += 7
    elif len(embedded_hits) == 1 and len(term) >= 11:
        penalty += 3

    if any(term.endswith(suffix) for suffix in DESCRIPTIVE_SUFFIXES):
        penalty += 3

    # Glue-word constructions such as map-for-love are especially literal.
    if "for" in embedded_hits and len(embedded_hits) >= 2:
        penalty += 5

    return penalty


def _distinctiveness_penalty(term: str) -> int:
    compact = term.lower()
    hits = {part for part in DESCRIPTIVE_NAME_PARTS if part in compact}

    if len(hits) < 2:
        return 0

    penalty = 6 + (len(hits) - 2) * 3
    if len(compact) >= 11:
        penalty += 3
    return min(15, penalty)


def _brand_independence_penalty(term: str) -> int:
    compact = term.lower()
    penalty = 0
    for marker, points in ESTABLISHED_NAME_MARKERS.items():
        if marker in compact:
            penalty += points
    for marker, points in GENERIC_PROJECT_MARKERS.items():
        if marker in compact:
            penalty += points
    if compact.startswith("git") or compact.endswith("git"):
        penalty += 10
    if compact.startswith("open") and len(compact) > 6:
        penalty += 3
    return min(25, penalty)


def _discovery_quality_penalty(repo: Repository) -> int:
    name_text = repo.name.lower().replace("-", " ").replace("_", " ")
    description_text = (repo.description or "").lower()
    combined = f"{name_text} {description_text}"

    words = set(combined.split())
    term_hits = {
        term
        for term in DERIVATIVE_TERMS
        if term in words
    }

    phrase_hits = {
        phrase
        for phrase in DERIVATIVE_PHRASES
        if phrase in combined
    }

    penalty = 0

    if term_hits:
        penalty += min(12, 5 + (len(term_hits) - 1) * 3)

    if phrase_hits:
        penalty += min(12, 7 + (len(phrase_hits) - 1) * 3)

    if any(
        marker in combined
        for marker in ("emulator", "recomp", "decomp", "reverse engineering")
    ):
        penalty += 8

    return min(20, penalty)


def _brandability_score(term: str) -> int:
    if not term:
        return 0

    letters = [c for c in term if c.isalpha()]
    if not letters:
        return 0

    score = 0
    vowel_ratio = sum(c in VOWELS for c in letters) / len(letters)

    if 0.28 <= vowel_ratio <= 0.62:
        score += 8
    elif 0.20 <= vowel_ratio <= 0.70:
        score += 4

    run = _longest_consonant_run(term)
    if run <= 2:
        score += 7
    elif run == 3:
        score += 3

    if term.isalpha():
        score += 3

    if not re.search(r"(.)\1\1", term):
        score += 2

    return min(20, score)


def score_repository(
    repo: Repository,
    search_term: str,
    *,
    com_available: bool = False,
    now: datetime | None = None,
) -> ScoreBreakdown:
    now = now or datetime.now(timezone.utc)
    term = search_term.lower().strip()
    tokens = _repo_tokens(repo.name)
    length = len(term)

    # NAME QUALITY: 0-30.
    if 4 <= length <= 8:
        length_score = 20
    elif 9 <= length <= 12:
        length_score = 18
    elif 13 <= length <= 15:
        length_score = 13
    elif 16 <= length <= 18:
        length_score = 8
    elif 19 <= length <= 21:
        length_score = 4
    elif length <= 3:
        length_score = 11
    else:
        length_score = 0

    structure_score = {1: 10, 2: 8, 3: 4, 4: 2}.get(len(tokens), 0)
    name_quality = min(30, length_score + structure_score)

    brandability = _brandability_score(term)

    # MARKET MOMENTUM: 0-25.
    # Stars/day is the primary signal; absolute stars add only a small
    # confirmation bonus.
    velocity = repo.stars / _age_days(repo.created_at, now=now)

    if velocity >= 200:
        velocity_score = 20
    elif velocity >= 100:
        velocity_score = 18
    elif velocity >= 50:
        velocity_score = 16
    elif velocity >= 25:
        velocity_score = 13
    elif velocity >= 10:
        velocity_score = 10
    elif velocity >= 5:
        velocity_score = 7
    elif velocity >= 2:
        velocity_score = 5
    elif velocity >= 1:
        velocity_score = 3
    elif velocity >= 0.5:
        velocity_score = 2
    else:
        velocity_score = 1

    if repo.stars >= 1000:
        star_score = 5
    elif repo.stars >= 500:
        star_score = 4
    elif repo.stars >= 200:
        star_score = 3
    elif repo.stars >= 50:
        star_score = 2
    elif repo.stars >= 10:
        star_score = 1
    else:
        star_score = 0

    momentum = min(25, velocity_score + star_score)
    com_bonus = 25 if com_available else 0

    penalties = min(
        24,
        sum(1 for token in tokens if token in NOISE_WORDS) * 10,
    )
    if any(fragment in term for fragment in TECH_FRAGMENTS):
        penalties += 8
    if any(char.isdigit() for char in term):
        penalties += 10
    if length >= 16:
        penalties += (length - 15) * 2
    if len(tokens) >= 4:
        penalties += (len(tokens) - 3) * 5
    if length > 24:
        penalties += 12
    if _longest_consonant_run(term) >= 4:
        penalties += 8

    penalties += _descriptive_phrase_penalty(term, tokens)
    penalties += _discovery_quality_penalty(repo)
    penalties += _brand_independence_penalty(term)
    penalties += _distinctiveness_penalty(term)

    candidate_score = max(
        0,
        min(
            75,
            name_quality + brandability + momentum - penalties,
        ),
    )

    opportunity_score = max(
        0,
        min(
            100,
            candidate_score + com_bonus,
        ),
    )

    return ScoreBreakdown(
        candidate_score=candidate_score,
        total=opportunity_score,
        name_quality=name_quality,
        brandability=brandability,
        momentum=momentum,
        com_bonus=com_bonus,
        penalties=penalties,
    )
