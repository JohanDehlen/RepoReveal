import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reporeveal.settings import (
    is_valid_geometry,
    load_window_geometry,
    save_window_geometry,
    settings_path,
)


class WindowSettingsTests(unittest.TestCase):
    def test_valid_geometry(self) -> None:
        self.assertTrue(is_valid_geometry("1120x650+100+50"))
        self.assertTrue(is_valid_geometry("1400x900-20+10"))
        self.assertFalse(is_valid_geometry("1120x650"))
        self.assertFalse(is_valid_geometry("not-a-geometry"))

    def test_uses_local_app_data(self) -> None:
        with patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Temp\Local"}, clear=False):
            self.assertEqual(
                settings_path(),
                Path(r"C:\Temp\Local") / "RepoReveal" / "settings.json",
            )

    def test_round_trip_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_path = Path(temp_dir) / "settings.json"
            with patch("reporeveal.settings.settings_path", return_value=fake_path):
                save_window_geometry("1280x720+20+30")
                self.assertEqual(
                    load_window_geometry(),
                    "1280x720+20+30",
                )

    def test_invalid_file_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_path = Path(temp_dir) / "settings.json"
            fake_path.write_text("{bad json", encoding="utf-8")
            with patch("reporeveal.settings.settings_path", return_value=fake_path):
                self.assertEqual(
                    load_window_geometry(default="900x600"),
                    "900x600",
                )

    def test_invalid_saved_geometry_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_path = Path(temp_dir) / "settings.json"
            fake_path.write_text(
                json.dumps({"window_geometry": "broken"}),
                encoding="utf-8",
            )
            with patch("reporeveal.settings.settings_path", return_value=fake_path):
                self.assertEqual(
                    load_window_geometry(default="900x600"),
                    "900x600",
                )


if __name__ == "__main__":
    unittest.main()