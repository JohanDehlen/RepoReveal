import unittest
from datetime import datetime, timezone

from reporip.business_client import RepositoryBusinessEvidence
from reporip.business_potential import analyze_business_potential
from reporip.models import Repository


NOW = datetime(2026, 8, 14, tzinfo=timezone.utc)


def make_repo(
    name="anti-slop",
    full_name="dmmulroy/anti-slop",
    description="",
    stars=50,
    language="TypeScript",
    created_at="2026-08-12T00:00:00Z",
):
    return Repository(
        name,
        full_name,
        stars,
        created_at,
        language,
        description,
        f"https://github.com/{full_name}",
    )


class BusinessPotentialTests(unittest.TestCase):
    def test_rich_developer_tool_has_strong_business_signal(self):
        evidence = RepositoryBusinessEvidence(
            readme_excerpt=(
                "Developer tool for engineering teams that detects risky code, "
                "automates code review, prevents errors, and improves production "
                "quality. Integrates into team workflows."
            ),
            topics=("developer-tools", "lint", "code-quality"),
            license_name="MIT",
            forks=12,
        )
        result = analyze_business_potential(
            make_repo(
                description=(
                    "Opinionated Oxlint rules for rejecting low-evidence "
                    "TypeScript and JavaScript patterns"
                ),
                stars=638,
            ),
            evidence,
            now=NOW,
        )
        self.assertEqual(result.archetype, "developer-tool")
        self.assertGreaterEqual(result.score, 75)
        self.assertEqual(result.confidence, "Medium")

    def test_kage_is_creative_and_commercially_gated(self):
        evidence = RepositoryBusinessEvidence(
            readme_excerpt=(
                "An interactive five-chapter night walk through a Kyoto mountain "
                "temple rendered live in Three.js. A creative coding and interactive "
                "storytelling experience using WebGL."
            ),
            topics=(
                "creative-coding",
                "generative-art",
                "interactive-storytelling",
                "japanese-design",
                "threejs",
                "webgl",
            ),
            homepage="https://mengto.github.io/kage/",
            forks=176,
        )
        result = analyze_business_potential(
            make_repo(
                name="kage",
                full_name="MengTo/kage",
                description=(
                    "An interactive five-chapter night walk through a Kyoto "
                    "mountain temple, rendered live in Three.js."
                ),
                stars=939,
                language="HTML",
                created_at="2026-08-08T00:00:00Z",
            ),
            evidence,
            now=NOW,
        )
        self.assertEqual(result.archetype, "creative-experience")
        self.assertLessEqual(result.score, 55)
        self.assertTrue(
            any("Commercial Evidence Gate" in item for item in result.inferred)
        )

    def test_popularity_alone_does_not_create_business_potential(self):
        evidence = RepositoryBusinessEvidence(
            readme_excerpt=(
                "A generative art experiment and interactive visual showcase."
            ),
            topics=("creative-coding", "generative-art"),
            forks=500,
        )
        result = analyze_business_potential(
            make_repo(
                name="beautiful-demo",
                full_name="artist/beautiful-demo",
                description="Interactive generative art experiment.",
                stars=10000,
                language="JavaScript",
            ),
            evidence,
            now=NOW,
        )
        self.assertEqual(result.momentum_score, 20)
        self.assertEqual(result.reach_score, 15)
        self.assertLessEqual(result.score, 55)

    def test_fractional_age_is_used(self):
        result = analyze_business_potential(make_repo(stars=638), now=NOW)
        self.assertTrue(
            any("319.0 stars/day" in item for item in result.observed)
        )

    def test_uncertainty_is_explicit(self):
        result = analyze_business_potential(make_repo(), now=NOW)
        self.assertTrue(
            any("not proven" in item.lower() for item in result.hypotheses)
        )


if __name__ == "__main__":
    unittest.main()
