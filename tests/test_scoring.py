import unittest
from datetime import datetime, timezone

from reporip.models import Repository
from reporip.scoring import score_repository

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

    def test_independent_project_beats_wrapper_with_same_name_shape(self) -> None:
        independent = Repository(
            name="Velora",
            full_name="owner/Velora",
            stars=300,
            created_at="2026-08-09T02:00:00Z",
            language="Python",
            description="A new collaborative visual workspace.",
            html_url="https://github.com/owner/Velora",
        )
        wrapper = Repository(
            name="Velora",
            full_name="owner/Velora-wrapper",
            stars=300,
            created_at="2026-08-09T02:00:00Z",
            language="Python",
            description="A lightweight wrapper for an existing API.",
            html_url="https://github.com/owner/Velora-wrapper",
        )

        independent_score = score_repository(
            independent,
            "velora",
            now=NOW,
        )
        wrapper_score = score_repository(
            wrapper,
            "velora",
            now=NOW,
        )

        self.assertGreater(
            independent_score.candidate_score,
            wrapper_score.candidate_score,
        )
        self.assertGreater(wrapper_score.penalties, independent_score.penalties)

    def test_emulator_project_receives_discovery_penalty(self) -> None:
        independent = Repository(
            name="Eden",
            full_name="owner/Eden",
            stars=300,
            created_at="2026-08-09T02:00:00Z",
            language="C++",
            description="Original real-time simulation engine.",
            html_url="https://github.com/owner/Eden",
        )
        emulator = Repository(
            name="Eden-Emulator",
            full_name="owner/Eden-Emulator",
            stars=300,
            created_at="2026-08-09T02:00:00Z",
            language="C++",
            description="Emulator and compatibility project.",
            html_url="https://github.com/owner/Eden-Emulator",
        )

        clean = score_repository(independent, "eden", now=NOW)
        derivative = score_repository(
            emulator,
            "edenemulator",
            now=NOW,
        )

        self.assertGreater(clean.candidate_score, derivative.candidate_score)
        self.assertGreaterEqual(derivative.penalties, 8)

    def test_reimplementation_phrase_is_penalized(self) -> None:
        original = Repository(
            name="Lumera",
            full_name="owner/Lumera",
            stars=100,
            created_at="2026-08-09T02:00:00Z",
            language="Rust",
            description="A new graphics toolkit.",
            html_url="https://github.com/owner/Lumera",
        )
        reimplementation = Repository(
            name="Lumera",
            full_name="owner/Lumera-reimpl",
            stars=100,
            created_at="2026-08-09T02:00:00Z",
            language="Rust",
            description="A reimplementation of an existing graphics toolkit.",
            html_url="https://github.com/owner/Lumera-reimpl",
        )

        clean = score_repository(original, "lumera", now=NOW)
        derivative = score_repository(
            reimplementation,
            "lumera",
            now=NOW,
        )

        self.assertGreater(clean.candidate_score, derivative.candidate_score)

    def test_git_prefixed_name_loses_brand_independence(self) -> None:
        clean = Repository(name="Knife", full_name="owner/Knife", stars=200, created_at="2026-08-10T02:00:00Z", language="TypeScript", description="A focused developer utility.", html_url="https://github.com/owner/Knife")
        tied = Repository(name="git-knife", full_name="owner/git-knife", stars=200, created_at="2026-08-10T02:00:00Z", language="TypeScript", description="A focused developer utility.", html_url="https://github.com/owner/git-knife")
        clean_score = score_repository(clean, "knife", now=NOW)
        tied_score = score_repository(tied, "gitknife", now=NOW)
        self.assertGreater(clean_score.candidate_score, tied_score.candidate_score)
        self.assertGreater(tied_score.penalties, clean_score.penalties)

    def test_arxiv_name_receives_established_marker_penalty(self) -> None:
        repo = Repository(name="neuroarxiv", full_name="owner/neuroarxiv", stars=300, created_at="2026-08-09T02:00:00Z", language="Python", description="Research workflow software.", html_url="https://github.com/owner/neuroarxiv")
        result = score_repository(repo, "neuroarxiv", now=NOW)
        self.assertGreaterEqual(result.penalties, 14)

    def test_existing_brand_name_is_heavily_penalized(self) -> None:
        repo = Repository(name="WeChat-AI", full_name="owner/WeChat-AI", stars=1500, created_at="2026-08-10T02:00:00Z", language="TypeScript", description="AI integration project.", html_url="https://github.com/owner/WeChat-AI")
        result = score_repository(repo, "wechat", now=NOW)
        self.assertGreaterEqual(result.penalties, 18)

    def test_distinctive_name_avoids_independence_penalty(self) -> None:
        repo = Repository(name="Limioryn", full_name="owner/Limioryn", stars=135, created_at="2026-08-07T02:00:00Z", language="Python", description="Independent edge-cloud framework.", html_url="https://github.com/owner/Limioryn")
        result = score_repository(repo, "limioryn", now=NOW)
        self.assertEqual(result.penalties, 0)

    def test_descriptive_compound_loses_to_distinctive_name(self) -> None:
        distinctive = Repository(name="Limioryn", full_name="owner/Limioryn", stars=200, created_at="2026-08-09T02:00:00Z", language="Python", description="Independent software project.", html_url="https://github.com/owner/Limioryn")
        descriptive = Repository(name="phone-harness", full_name="owner/phone-harness", stars=200, created_at="2026-08-09T02:00:00Z", language="Python", description="Independent software project.", html_url="https://github.com/owner/phone-harness")
        brand = score_repository(distinctive, "limioryn", now=NOW)
        compound = score_repository(descriptive, "phoneharness", now=NOW)
        self.assertGreater(brand.candidate_score, compound.candidate_score)
        self.assertGreater(compound.penalties, brand.penalties)

    def test_oilmotion_receives_distinctiveness_penalty(self) -> None:
        repo = Repository(name="oil-motion", full_name="owner/oil-motion", stars=200, created_at="2026-08-09T02:00:00Z", language="Python", description="Interactive animation project.", html_url="https://github.com/owner/oil-motion")
        result = score_repository(repo, "oilmotion", now=NOW)
        self.assertGreaterEqual(result.penalties, 6)

    def test_humanwriting_receives_distinctiveness_penalty(self) -> None:
        repo = Repository(name="human-writing", full_name="owner/human-writing", stars=200, created_at="2026-08-09T02:00:00Z", language="Python", description="Writing software.", html_url="https://github.com/owner/human-writing")
        result = score_repository(repo, "humanwriting", now=NOW)
        self.assertGreaterEqual(result.penalties, 6)

    def test_short_distinctive_names_are_not_hit(self) -> None:
        for name in ("limioryn", "kadath", "vocat", "kage"):
            repo = Repository(name=name, full_name=f"owner/{name}", stars=100, created_at="2026-08-09T02:00:00Z", language="Python", description="Independent software project.", html_url=f"https://github.com/owner/{name}")
            result = score_repository(repo, name, now=NOW)
            self.assertEqual(result.penalties, 0, f"{name} should not receive a distinctiveness penalty")


if __name__ == "__main__":
    unittest.main()
