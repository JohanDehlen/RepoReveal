import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from reporeveal.domain_checker import (
    DomainStatus,
    SUPPORTED_TLDS,
    candidate_domains,
    check_domain_io_whois,
    check_domain_rdap,
    normalize_repo_name,
)


class FakeResponse:
    def __init__(self, payload: object | None = None) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class DomainNameTests(unittest.TestCase):
    def test_normalizes_repo_names(self) -> None:
        self.assertEqual(normalize_repo_name("Cool_Project"), "coolproject")
        self.assertEqual(normalize_repo_name("  My App!  "), "myapp")
        self.assertEqual(normalize_repo_name("--A---B--"), "ab")
        self.assertEqual(normalize_repo_name("Repo-Reveal"), "reporeveal")
        self.assertEqual(normalize_repo_name("WeChat-AI"), "wechat")
        self.assertEqual(normalize_repo_name("my-tool-dev"), "mytool")
        self.assertEqual(normalize_repo_name("project-online"), "project")
        self.assertEqual(normalize_repo_name("telecom"), "telecom")

    def test_builds_all_supported_candidates(self) -> None:
        domains = candidate_domains("RepoReveal")
        self.assertEqual(len(domains), 8)
        self.assertEqual(domains[0], "reporeveal.com")
        self.assertEqual(domains[-1], "reporeveal.site")
        self.assertEqual(
            SUPPORTED_TLDS,
            ("com", "net", "org", "dev", "io", "ai", "online", "site"),
        )


class FakeSocket:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.sent = b""
        self._done = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def settimeout(self, _timeout):
        pass

    def sendall(self, data):
        self.sent += data

    def recv(self, _size):
        if self._done:
            return b""
        self._done = True
        return self.payload


class IoWhoisTests(unittest.TestCase):
    def test_registered_io_is_taken(self) -> None:
        fake = FakeSocket(
            b"Domain Name: example.io\r\nRegistry Domain ID: REDACTED\r\n"
        )
        with patch(
            "reporeveal.domain_checker.socket.create_connection",
            return_value=fake,
        ):
            result = check_domain_io_whois("example.io")
        self.assertEqual(result.status, DomainStatus.TAKEN)
        self.assertEqual(fake.sent, b"example.io\r\n")

    def test_unregistered_io_is_available(self) -> None:
        fake = FakeSocket(b"Domain not found.\r\n")
        with patch(
            "reporeveal.domain_checker.socket.create_connection",
            return_value=fake,
        ):
            result = check_domain_io_whois("unlikely-name.io")
        self.assertEqual(result.status, DomainStatus.AVAILABLE)

    def test_unrecognized_io_response_is_unknown(self) -> None:
        fake = FakeSocket(b"Temporary service message\r\n")
        with patch(
            "reporeveal.domain_checker.socket.create_connection",
            return_value=fake,
        ):
            result = check_domain_io_whois("example.io")
        self.assertEqual(result.status, DomainStatus.UNKNOWN)

class RdapTests(unittest.TestCase):
    def _bootstrap(self):
        return FakeResponse(
            {"services": [[["com"], ["https://rdap.example/"]]]}
        )

    def test_existing_domain_is_taken(self) -> None:
        with patch(
            "reporeveal.domain_checker.urllib.request.urlopen",
            side_effect=[self._bootstrap(), FakeResponse({})],
        ):
            result = check_domain_rdap("example.com")
        self.assertEqual(result.status, DomainStatus.TAKEN)

    def test_404_is_available(self) -> None:
        error = urllib.error.HTTPError(
            "https://rdap.example/domain/example.com",
            404,
            "Not Found",
            {},
            io.BytesIO(),
        )
        with patch(
            "reporeveal.domain_checker.urllib.request.urlopen",
            side_effect=[self._bootstrap(), error],
        ):
            result = check_domain_rdap("example.com")
        self.assertEqual(result.status, DomainStatus.AVAILABLE)

    def test_rate_limit_is_unknown(self) -> None:
        error = urllib.error.HTTPError(
            "https://rdap.example/domain/example.com",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(),
        )
        with patch(
            "reporeveal.domain_checker.urllib.request.urlopen",
            side_effect=[self._bootstrap(), error],
        ):
            result = check_domain_rdap("example.com")
        self.assertEqual(result.status, DomainStatus.UNKNOWN)


if __name__ == "__main__":
    unittest.main()