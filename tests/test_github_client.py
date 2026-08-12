import unittest
from datetime import datetime, timezone

from reporeveal.github_client import build_search_query


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


if __name__ == "__main__":
    unittest.main()
