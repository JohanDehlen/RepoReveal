from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from .business_client import RepositoryBusinessEvidence
from .models import Repository


@dataclass(frozen=True, slots=True)
class BusinessPotential:
    score: int
    confidence: str
    pain_score: int
    buyer_score: int
    product_score: int
    reach_score: int
    momentum_score: int
    archetype: str
    likely_buyer: str
    purchased_value: str
    business_model: str
    validation_move: str
    observed: tuple[str, ...]
    inferred: tuple[str, ...]
    hypotheses: tuple[str, ...]


_ARCHETYPES = (
    (
        "developer-tool",
        (
            "developer tool", "developer-tools", "linter", "lint",
            "code quality", "code-quality", "code review", "static analysis",
            "sdk", "api", "plugin", "ide", "repository", "repositories",
            "git workflow", "testing", "test runner", "debugger", "compiler",
            "formatter",
        ),
        "Software teams or developer-tool companies",
        "Save engineering time, standardize quality, or reduce integration and maintenance risk",
        "Free local/core tool + paid team workflow, integrations, support, or enterprise controls",
        "Find 10 teams using comparable tooling and ask which quality, rollout, or maintenance failure costs them the most.",
    ),
    (
        "automation",
        (
            "automate", "automation", "workflow", "pipeline", "orchestration",
            "repetitive", "manual process", "scheduled", "integration workflow",
        ),
        "Teams repeatedly performing the workflow",
        "Remove repetitive labor and make a recurring process more reliable",
        "Free/basic workflow + paid automation, coordination, managed operation, or support",
        "Identify 10 people doing the workflow repeatedly and test whether they would pay to remove one costly manual step.",
    ),
    (
        "infrastructure",
        (
            "observability", "monitoring", "security", "server", "database",
            "deployment", "deploy", "storage", "infrastructure", "proxy",
            "self-hosted", "kubernetes", "docker", "incident", "uptime",
        ),
        "Engineering or platform teams running the capability in production",
        "Reduce operational risk, downtime, maintenance burden, or infrastructure complexity",
        "Open core + paid hosted operation, reliability, governance, private deployment, or SLA",
        "Find 10 production users and ask which operational failure or maintenance task creates budget-worthy pain.",
    ),
    (
        "data-ai",
        (
            "llm", "rag", "inference", "ocr", "machine learning", "embedding",
            "vector database", "document processing", "model serving",
            "data pipeline", "ai agent", "vision model",
        ),
        "Teams whose product or operations depend on the data or AI outcome",
        "Improve quality or throughput while reducing manual review and integration work",
        "Open tooling + paid hosted processing, higher-volume workflows, monitoring, or enterprise deployment",
        "Find 10 teams using similar pipelines and test the most expensive quality, scale, or reliability failure.",
    ),
)

_CREATIVE_TERMS = (
    "creative-coding", "creative coding", "generative-art", "generative art",
    "interactive-storytelling", "interactive storytelling", "art project",
    "artwork", "portfolio", "showcase", "visual experiment",
    "interactive experience", "storytelling", "game jam", "museum",
    "installation",
)

_COMMERCIAL_PAIN_TERMS = (
    "reduce", "save time", "automate", "monitor", "secure", "security",
    "reliability", "prevent", "production", "reject", "detect", "validate",
    "verify", "audit", "quality", "error", "errors", "risk", "compliance",
    "review", "debug", "incident", "manual", "maintenance", "cost",
    "workflow", "repetitive", "downtime", "governance",
)

_BUYER_TERMS = (
    "team", "teams", "enterprise", "business", "company", "companies",
    "organization", "organizations", "customer", "customers", "agency",
    "agencies", "engineering team", "platform team", "developer team",
    "maintainers",
)

_PRODUCT_TERMS = (
    "api", "platform", "hosted", "service", "server", "cli", "sdk",
    "integration", "workflow", "tool", "agent", "app", "plugin", "package",
    "library", "extension", "dashboard", "self-hosted",
)

_PURCHASE_TERMS = (
    "pricing", "paid", "subscription", "enterprise", "hosted", "cloud",
    "support", "commercial", "pro plan", "team plan", "managed service",
    "customers", "customer",
)


def _clean_readme(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _evidence_text(repo: Repository, evidence: RepositoryBusinessEvidence) -> str:
    return " ".join(
        [
            repo.name,
            repo.description,
            repo.language,
            " ".join(evidence.topics),
            _clean_readme(evidence.readme_excerpt)[:6000],
        ]
    ).lower()


def _count_terms(text: str, terms: tuple[str, ...]) -> int:
    return sum(1 for term in terms if term in text)


def _classify(repo: Repository, evidence: RepositoryBusinessEvidence):
    text = _evidence_text(repo, evidence)
    creative_hits = _count_terms(text, _CREATIVE_TERMS)

    if creative_hits >= 2:
        return (
            "creative-experience",
            "Audience, patrons, publishers, cultural organizations, or brands if a paying use case exists",
            "Entertainment, artistic experience, audience engagement, or creative differentiation",
            "Commercialization is unproven; possible paths include commissions, licensing, sponsorship, publishing, or paid experiences",
            "Identify who receives measurable value beyond GitHub attention and test whether that group has a budget for the experience.",
        )

    best = None
    best_hits = 0
    for entry in _ARCHETYPES:
        hits = _count_terms(text, entry[1])
        if hits > best_hits:
            best = entry
            best_hits = hits

    if best is not None and best_hits >= 2:
        return best[0], best[2], best[3], best[4], best[5]

    return (
        "general-software",
        "Users or teams for whom the project replaces a recurring workaround",
        "Save time, reduce risk, or provide a capability that is expensive to recreate",
        "Keep the useful core free; test paid support, implementation, managed operation, or a focused pro workflow",
        "Find 10 real users and ask what recurring job they would be disappointed to lose.",
    )


def _momentum(repo: Repository, now: datetime):
    try:
        created = datetime.fromisoformat(repo.created_at.replace("Z", "+00:00"))
        age_days = max(0.25, (now - created).total_seconds() / 86400)
    except (ValueError, TypeError):
        age_days = 30.0

    rate = repo.stars / age_days
    if rate >= 100:
        return 20, f"Exceptional early attention: about {rate:.1f} stars/day."
    if rate >= 25:
        return 18, f"Very strong early attention: about {rate:.1f} stars/day."
    if rate >= 10:
        return 15, f"Strong early attention: about {rate:.1f} stars/day."
    if rate >= 3:
        return 11, f"Meaningful early attention: about {rate:.1f} stars/day."
    if rate >= 1:
        return 7, f"Some early attention: about {rate:.1f} stars/day."
    if repo.stars >= 20:
        return 4, f"Some adoption signal: {repo.stars} stars."
    return 2, f"Limited adoption evidence so far: {repo.stars} stars."


def analyze_business_potential(
    repo: Repository,
    evidence: RepositoryBusinessEvidence | None = None,
    *,
    now: datetime | None = None,
) -> BusinessPotential:
    evidence = evidence or RepositoryBusinessEvidence()
    now = now or datetime.now(timezone.utc)
    text = _evidence_text(repo, evidence)

    archetype, buyer, value, model, validation = _classify(repo, evidence)

    pain_hits = _count_terms(text, _COMMERCIAL_PAIN_TERMS)
    buyer_hits = _count_terms(text, _BUYER_TERMS)
    product_hits = _count_terms(text, _PRODUCT_TERMS)
    purchase_hits = _count_terms(text, _PURCHASE_TERMS)
    creative_hits = _count_terms(text, _CREATIVE_TERMS)

    pain_score = min(25, 5 + pain_hits * 3)
    buyer_score = min(20, 4 + buyer_hits * 3)
    product_score = min(20, 5 + product_hits * 3)

    if archetype == "creative-experience":
        pain_score = min(pain_score, 8)
        buyer_score = min(buyer_score, 7)
        product_score = min(product_score, 8)

    if repo.stars >= 500:
        reach_score = 15
    elif repo.stars >= 150:
        reach_score = 13
    elif repo.stars >= 50:
        reach_score = 10
    elif repo.stars >= 10:
        reach_score = 7
    else:
        reach_score = 4

    if evidence.forks >= 10:
        reach_score = min(15, reach_score + 1)

    momentum_score, momentum_note = _momentum(repo, now)

    raw_score = min(
        100,
        pain_score + buyer_score + product_score + reach_score + momentum_score,
    )

    strong_dimensions = sum(
        (
            pain_score >= 14,
            buyer_score >= 10,
            product_score >= 12,
        )
    )
    explicit_purchase_signal = purchase_hits >= 1

    gate_note = ""
    if archetype == "creative-experience" and not explicit_purchase_signal:
        score = min(raw_score, 55)
        gate_note = (
            "Commercial Evidence Gate: strong attention cannot lift a creative "
            "experience above 55 without evidence of a paying use case."
        )
    elif strong_dimensions == 0 and not explicit_purchase_signal:
        score = min(raw_score, 55)
        gate_note = (
            "Commercial Evidence Gate: no strong pain, buyer, or product "
            "dimension is yet supported."
        )
    elif strong_dimensions == 1 and not explicit_purchase_signal:
        score = min(raw_score, 69)
        gate_note = (
            "Commercial Evidence Gate: only one strong commercial dimension "
            "is currently supported."
        )
    else:
        score = raw_score

    observed = [
        f"Repository: {repo.full_name}",
        f"Description: {repo.description or 'No description supplied'}",
        f"Primary language: {repo.language or 'Unknown'}",
        f"Stars at discovery: {repo.stars}",
        momentum_note,
    ]

    if evidence.topics:
        observed.append(f"GitHub topics: {', '.join(evidence.topics[:8])}")
    if evidence.license_name:
        observed.append(f"License: {evidence.license_name}")
    if evidence.forks:
        observed.append(f"Forks: {evidence.forks}")
    if evidence.homepage:
        observed.append(f"Project homepage: {evidence.homepage}")
    if evidence.readme_excerpt:
        observed.append("README evidence was included in this analysis.")

    inferred = [
        f"Project archetype: {archetype}",
        f"Likely buyer: {buyer}",
        f"Purchased value: {value}",
    ]

    if creative_hits >= 2:
        inferred.append(
            "Project-purpose evidence indicates a creative/experiential project; "
            "implementation technology was not treated as proof of a developer-tool business."
        )

    if gate_note:
        inferred.append(gate_note)

    rich = (
        int(bool(evidence.readme_excerpt))
        + int(bool(evidence.topics))
        + int(bool(evidence.license_name))
    )
    confidence = (
        "Medium"
        if rich >= 2
        else "Low-Medium"
        if rich >= 1 or repo.description.strip()
        else "Low"
    )

    hypotheses = [
        f"Business model candidate: {model}",
        f"First validation move: {validation}",
        "Willingness to pay is not proven by repository evidence, GitHub activity, forks, or stars.",
    ]

    return BusinessPotential(
        score=score,
        confidence=confidence,
        pain_score=pain_score,
        buyer_score=buyer_score,
        product_score=product_score,
        reach_score=reach_score,
        momentum_score=momentum_score,
        archetype=archetype,
        likely_buyer=buyer,
        purchased_value=value,
        business_model=model,
        validation_move=validation,
        observed=tuple(observed),
        inferred=tuple(inferred),
        hypotheses=tuple(hypotheses),
    )
