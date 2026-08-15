import base64
import io
import json
import unittest
from unittest.mock import patch
from reporip.business_client import fetch_repository_business_evidence
from reporip.models import Repository

class Response(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *args): self.close()

class BusinessClientTests(unittest.TestCase):
    @patch("reporip.business_client.urlopen")
    def test_fetches_metadata_and_readme(self, mock_urlopen):
        metadata = {
            "topics": ["developer-tools", "automation"],
            "homepage": "https://example.com",
            "license": {"spdx_id": "MIT"},
            "forks_count": 12,
            "open_issues_count": 3,
        }
        readme = {
            "content": base64.b64encode(
                b"Engineering teams automate risky review work."
            ).decode("ascii")
        }
        mock_urlopen.side_effect = [
            Response(json.dumps(metadata).encode()),
            Response(json.dumps(readme).encode()),
        ]
        repo = Repository(
            "demo", "owner/demo", 100, "2026-08-12T00:00:00Z",
            "Python", "Developer tool", "https://github.com/owner/demo",
        )
        result = fetch_repository_business_evidence(repo)
        self.assertEqual(result.license_name, "MIT")
        self.assertEqual(result.forks, 12)
        self.assertIn("Engineering teams", result.readme_excerpt)
