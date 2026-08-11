from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Repository:
    name: str
    full_name: str
    stars: int
    created_at: str
    language: str
    description: str
    html_url: str