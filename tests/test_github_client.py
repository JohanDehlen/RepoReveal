import io
import json
import unittest
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from reporeveal.github_client import build_search_query, search_repositories


class BuildSearchQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)

    def test_builds_date_and_star_filters(self) -> None:
        query = build_search_query(days=7, min_stars=10, now=self.now)
        self.assertEqual(query, "created:>=2026-08-04 stars:>=10")

    def test_adds_category_when_supplied(self) -> None:
        query = build_search_query(
            days=7,
            min_stars=10,
            category="music",
            now=self.now,
        )
        self.assertTrue(query.startswith("music "))
        self.assertIn("created:>=2026-08-04", query)
        self.assertIn("stars:>=10", query)

    def test_adds_language_when_supplied(self) -> None:
        query = build_search_query(
            days=1,
            min_stars=0,
            language=" Python ",
            now=self.now,
        )
        self.assertEqual(
            query,
            "created:>=2026-08-10 stars:>=0 language:Python",
        )

    def test_rejects_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            build_search_query(days=0, min_stars=1, now=self.now)
        with self.assertRaises(ValueError):
            build_search_query(days=1, min_stars=-1, now=self.now)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
        return False


class SearchRepositoriesTests(unittest.TestCase):
    @staticmethod
    def _response(items):
        payload = json.dumps({"items": items}).encode("utf-8")
        return FakeResponse(payload)

    @staticmethod
    def _item(index: int) -> dict[str, object]:
        return {
            "name": f"repo-{index}",
            "full_name": f"owner/repo-{index}",
            "stargazers_count": 1000 - index,
            "created_at": "2026-08-10T00:00:00Z",
            "language": "Python",
            "description": "",
            "html_url": f"https://github.com/owner/repo-{index}",
        }

    def test_paginates_candidate_pool_beyond_100(self) -> None:
        pages = [
            self._response([self._item(i) for i in range(100)]),
            self._response([self._item(i) for i in range(100, 200)]),
            self._response([self._item(i) for i in range(200, 250)]),
        ]

        with patch(
            "reporeveal.github_client.urlopen",
            side_effect=pages,
        ) as mocked:
            results = search_repositories(
                days=7,
                min_stars=10,
                max_results=250,
            )

        self.assertEqual(len(results), 250)
        self.assertEqual(mocked.call_count, 3)

        urls = [
            call.args[0].full_url
            for call in mocked.call_args_list
        ]
        queries = [parse_qs(urlparse(url).query) for url in urls]

        self.assertEqual(queries[0]["per_page"], ["100"])
        self.assertEqual(queries[0]["page"], ["1"])
        self.assertEqual(queries[1]["per_page"], ["100"])
        self.assertEqual(queries[1]["page"], ["2"])
        self.assertEqual(queries[2]["per_page"], ["50"])
        self.assertEqual(queries[2]["page"], ["3"])

    def test_rejects_candidate_pool_above_300(self) -> None:
        with self.assertRaises(ValueError):
            search_repositories(max_results=301)


if __name__ == "__main__":
    unittest.main()
