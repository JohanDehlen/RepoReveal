import unittest
from datetime import datetime, timezone

from reporeveal.models import Repository
from reporeveal.scoring import score_repository

NOW = datetime(2026, 8, 12, 2, 0, tzinfo=timezone.utc)


def repo(name: str, stars: int = 300, created_at: str = "2026-08-09T02:00:00Z") -> Repository:
    return Repository(
        name=name,
        full_name=f"owner/{name}",
        stars=stars,
        created_at=created_at,
        language="Python",
        description="",
        html_url="https://github.com/owner/repo",
    )


class RepositoryScoreTests(unittest.TestCase):
    def score(self, name: str, term: str, stars: int = 300, com: bool = True):
        return score_repository(repo(name, stars), term, com_available=com, now=NOW)

    def test_short_brandable_name_scores_high(self) -> None:
        self.assertGreaterEqual(self.score("Kage", "kage", 800).total, 80)

    def test_available_com_adds_25(self) -> None:
        without = self.score("Fuxi", "fuxi", 400, False)
        with_com = self.score("Fuxi", "fuxi", 400, True)
        self.assertEqual(with_com.total - without.total, 25)

    def test_natural_name_beats_awkward_abbreviation(self) -> None:
        self.assertGreater(
            self.score("Kage", "kage").total,
            self.score("MemKB", "memkb").total,
        )

    def test_consonant_heavy_name_is_penalized(self) -> None:
        self.assertGreater(
            self.score("Nara", "nara").total,
            self.score("TCPFit", "tcpfit").total,
        )

    def test_long_descriptive_name_loses_to_brand(self) -> None:
        self.assertGreater(
            self.score("CallDiff", "calldiff").total,
            self.score("photo-abstract-editorial", "photoabstracteditorial", 2500).total,
        )

    def test_skill_name_is_penalized(self) -> None:
        self.assertGreater(
            self.score("Shuhao", "shuhao").total,
            self.score("shuhao-skills", "shuhaoskills", 900).total,
        )

    def test_version_number_is_penalized(self) -> None:
        self.assertGreater(
            self.score("Quake", "quake", 350).total,
            self.score("Quake_4_Alpha", "quake4alpha", 350).total,
        )

    def test_fast_rising_repo_strongly_beats_slow_repo(self) -> None:
        fast = score_repository(
            repo("Nova", 900, "2026-08-06T02:00:00Z"),
            "nova",
            com_available=False,
            now=NOW,
        )
        slow = score_repository(
            repo("Nova", 20, "2026-07-10T02:00:00Z"),
            "nova",
            com_available=False,
            now=NOW,
        )
        self.assertGreaterEqual(fast.momentum - slow.momentum, 12)

    def test_absolute_stars_are_secondary_to_velocity(self) -> None:
        fast = score_repository(
            repo("Nara", 300, "2026-08-11T02:00:00Z"),
            "nara",
            com_available=False,
            now=NOW,
        )
        old = score_repository(
            repo("Nara", 700, "2026-05-01T02:00:00Z"),
            "nara",
            com_available=False,
            now=NOW,
        )
        self.assertGreater(fast.momentum, old.momentum)

    def test_arrowescape_beats_mapforlove(self) -> None:
        arrow = self.score("ArrowEscape", "arrowescape", 29)
        literal = self.score("map-for-love", "mapforlove", 29)
        self.assertGreater(arrow.total, literal.total)

    def test_descriptive_web_name_is_penalized(self) -> None:
        clean = self.score("Velora", "velora", 30)
        descriptive = self.score("pi-lovely-web", "pilovelyweb", 30)
        self.assertGreater(clean.total, descriptive.total)

    def test_lab_phrase_is_penalized(self) -> None:
        clean = self.score("Lumera", "lumera", 60)
        descriptive = self.score("LovelyMiscLab", "lovelymisclab", 60)
        self.assertGreater(clean.total, descriptive.total)

    def test_music_descriptor_does_not_zero_out_candidate(self) -> None:
        result = self.score("CyShineMusic", "cyshinemusic", 25)
        self.assertGreater(result.total, 35)

    def test_candidate_score_is_domain_independent(self) -> None:
        without = self.score("Velora", "velora", 300, False)
        with_com = self.score("Velora", "velora", 300, True)
        self.assertEqual(without.candidate_score, with_com.candidate_score)

    def test_candidate_score_never_exceeds_75(self) -> None:
        result = self.score("Kage", "kage", 5000, True)
        self.assertLessEqual(result.candidate_score, 75)
        self.assertLessEqual(result.total, 100)

    def test_domain_check_can_reverse_preliminary_ranking(self) -> None:
        stronger = self.score("Nara", "nara", 800, False)
        weaker = self.score("Velora", "velora", 100, False)

        self.assertGreater(
            stronger.candidate_score,
            weaker.candidate_score,
        )

        weaker_with_com = self.score("Velora", "velora", 100, True)

        self.assertGreater(
            weaker_with_com.total,
            stronger.total,
        )


if __name__ == "__main__":
    unittest.main()
