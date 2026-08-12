import io
import json
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from reporeveal.collision_client import (
    GitHubCollisionError,
    check_github_collision,
)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


def response(payload: dict[str, object]) -> FakeResponse:
    return FakeResponse(json.dumps(payload).encode("utf-8"))


class CollisionTests(unittest.TestCase):
    def test_excludes_current_repository_and_counts_exact_names(self) -> None:
        repository_payload = {
            "items": [
                {
                    "name": "Repo-Diver",
                    "full_name": "me/Repo-Diver",
                },
                {
                    "name": "repodiver",
                    "full_name": "other/repodiver",
                    "stargazers_count": 42,
                    "created_at": "2025-01-02T03:04:05Z",
                    "description": "Existing project",
                    "html_url": "https://github.com/other/repodiver",
                },
                {
                    "name": "repodiver-demo",
                    "full_name": "other/repodiver-demo",
                },
            ]
        }
        user_payload = {"login": "repodiver"}

        with patch(
            "reporeveal.collision_client.urlopen",
            side_effect=[
                response(repository_payload),
                response(user_payload),
            ],
        ):
            result = check_github_collision(
                "Repo-Diver",
                current_full_name="me/Repo-Diver",
            )

        self.assertEqual(result.search_term, "repodiver")
        self.assertEqual(result.other_repositories, 1)
        self.assertTrue(result.exact_account)
        self.assertEqual(len(result.repository_matches), 1)
        match = result.repository_matches[0]
        self.assertEqual(match.full_name, "other/repodiver")
        self.assertEqual(match.stars, 42)
        self.assertEqual(match.created_at, "2025-01-02T03:04:05Z")
        self.assertEqual(match.description, "Existing project")
        self.assertEqual(
            match.html_url,
            "https://github.com/other/repodiver",
        )

    def test_404_account_means_no_exact_account(self) -> None:
        error = HTTPError(
            "https://api.github.com/users/velora",
            404,
            "Not Found",
            hdrs=None,
            fp=io.BytesIO(b'{"message":"Not Found"}'),
        )

        with patch(
            "reporeveal.collision_client.urlopen",
            side_effect=[
                response({"items": []}),
                error,
            ],
        ):
            result = check_github_collision("velora")

        self.assertEqual(result.other_repositories, 0)
        self.assertFalse(result.exact_account)

    def test_search_error_is_reported(self) -> None:
        error = HTTPError(
            "https://api.github.com/search/repositories",
            403,
            "Forbidden",
            hdrs=None,
            fp=io.BytesIO(b'{"message":"rate limit"}'),
        )

        with patch(
            "reporeveal.collision_client.urlopen",
            side_effect=error,
        ):
            with self.assertRaises(GitHubCollisionError):
                check_github_collision("velora")

    def test_rejects_empty_term(self) -> None:
        with self.assertRaises(ValueError):
            check_github_collision("---")

    def test_matches_are_sorted_by_stars(self) -> None:
        repository_payload = {
            "items": [
                {
                    "name": "velora",
                    "full_name": "low/velora",
                    "stargazers_count": 2,
                    "created_at": "2024-01-01T00:00:00Z",
                    "description": "",
                    "html_url": "https://github.com/low/velora",
                },
                {
                    "name": "Velora",
                    "full_name": "high/Velora",
                    "stargazers_count": 200,
                    "created_at": "2024-02-01T00:00:00Z",
                    "description": "",
                    "html_url": "https://github.com/high/Velora",
                },
            ]
        }

        account_404 = HTTPError(
            "https://api.github.com/users/velora",
            404,
            "Not Found",
            hdrs=None,
            fp=io.BytesIO(b'{"message":"Not Found"}'),
        )

        with patch(
            "reporeveal.collision_client.urlopen",
            side_effect=[
                response(repository_payload),
                account_404,
            ],
        ):
            result = check_github_collision("velora")

        self.assertEqual(
            [match.full_name for match in result.repository_matches],
            ["high/Velora", "low/velora"],
        )


if __name__ == "__main__":
    unittest.main()
