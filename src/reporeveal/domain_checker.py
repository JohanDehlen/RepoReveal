from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import socket


SUPPORTED_TLDS = (
    "com",
    "net",
    "org",
    "dev",
    "io",
    "ai",
    "online",
    "site",
)

_LABEL_RE = re.compile(r"[^a-z0-9-]+")


class DomainStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    TAKEN = "TAKEN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class DomainResult:
    domain: str
    status: DomainStatus
    detail: str = ""


def normalize_repo_name(name: str) -> str:
    raw = name.strip().lower()

    # If the repo name explicitly ends with one of our supported TLDs as
    # a separate token, treat that token as an extension hint rather than
    # part of the brand. Example: "WeChat-AI" -> "wechat".
    tokens = [
        token
        for token in re.split(r"[^a-z0-9]+", raw)
        if token
    ]
    if len(tokens) > 1 and tokens[-1] in SUPPORTED_TLDS:
        tokens = tokens[:-1]

    label = "".join(tokens)
    return label[:63]


def candidate_domains(repo_name: str) -> tuple[str, ...]:
    label = normalize_repo_name(repo_name)
    if not label:
        return ()
    return tuple(f"{label}.{tld}" for tld in SUPPORTED_TLDS)


def _rdap_bootstrap_url(tld: str, timeout: float) -> str | None:
    request = urllib.request.Request(
        "https://data.iana.org/rdap/dns.json",
        headers={"User-Agent": "RepoReveal/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)

    for service in payload.get("services", []):
        if not isinstance(service, list) or len(service) != 2:
            continue
        tlds, urls = service
        if tld in tlds and urls:
            return str(urls[0]).rstrip("/") + "/"
    return None


def check_domain_io_whois(domain: str, *, timeout: float = 8.0) -> DomainResult:
    domain = domain.strip().lower().rstrip(".")
    if not domain.endswith(".io"):
        return DomainResult(domain, DomainStatus.UNKNOWN, "Not an .io domain")

    try:
        with socket.create_connection(("whois.nic.io", 43), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall((domain + "\r\n").encode("ascii"))
            chunks: list[bytes] = []
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                chunks.append(data)

        text = b"".join(chunks).decode("utf-8", errors="replace")
        lowered = text.lower()

        if "domain not found." in lowered:
            return DomainResult(
                domain,
                DomainStatus.AVAILABLE,
                "No .io WHOIS registration record found",
            )

        if "domain name:" in lowered:
            return DomainResult(domain, DomainStatus.TAKEN, ".io WHOIS record found")

        return DomainResult(domain, DomainStatus.UNKNOWN, "Unrecognized .io WHOIS response")

    except (OSError, TimeoutError, UnicodeError) as exc:
        return DomainResult(domain, DomainStatus.UNKNOWN, type(exc).__name__)

def check_domain_rdap(domain: str, *, timeout: float = 8.0) -> DomainResult:
    domain = domain.strip().lower().rstrip(".")
    if "." not in domain:
        return DomainResult(domain, DomainStatus.UNKNOWN, "Invalid domain")

    tld = domain.rsplit(".", 1)[1]
    if tld not in SUPPORTED_TLDS:
        return DomainResult(domain, DomainStatus.UNKNOWN, "Unsupported TLD")

    if tld == "io":
        return check_domain_io_whois(domain, timeout=timeout)

    try:
        base_url = _rdap_bootstrap_url(tld, timeout)
        if not base_url:
            return DomainResult(domain, DomainStatus.UNKNOWN, "No RDAP service found")

        url = base_url + "domain/" + urllib.parse.quote(domain, safe=".-")
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/rdap+json, application/json",
                "User-Agent": "RepoReveal/0.1",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout):
            return DomainResult(domain, DomainStatus.TAKEN, "RDAP record found")

    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return DomainResult(
                domain,
                DomainStatus.AVAILABLE,
                "No RDAP registration record found",
            )
        if exc.code == 429:
            return DomainResult(domain, DomainStatus.UNKNOWN, "RDAP rate limited")
        return DomainResult(domain, DomainStatus.UNKNOWN, f"RDAP HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        return DomainResult(domain, DomainStatus.UNKNOWN, type(exc).__name__)