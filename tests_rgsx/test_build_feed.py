import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.build_feed import build_config, build_items, clean_title, generate_feed, normalize_game_entry


class BuildFeedUnitTests(unittest.TestCase):
    def test_normalize_array_entry_and_title_cleanup(self) -> None:
        raw_entry = [
            "Mega Example (USA).zip",
            "https://example.com/roms/Mega%20Example%20%28USA%29.zip",
            "512K",
        ]

        normalized = normalize_game_entry(raw_entry)
        self.assertEqual(normalized["title"], raw_entry[0])

        rom_url = normalized["url"]
        self.assertTrue(rom_url.endswith(".zip"))

        cleaned_title = clean_title(normalized.get("title"), rom_url)
        self.assertEqual(cleaned_title, "Mega Example (USA)")

        items = build_items([raw_entry], "nes", None)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["props"]["rom"], rom_url)
        self.assertEqual(items[0]["title"], cleaned_title)


class BuildFeedIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = Path(__file__).resolve().parents[1]
        cls.sample_cache = cls.repo_root / "saves_ports_rgsx"
        if not cls.sample_cache.exists():
            raise unittest.SkipTest("Sample RGSX cache data is not available.")

    def test_generate_feed_from_sample_cache(self) -> None:
        env_backup = os.environ.copy()
        try:
            os.environ["RGSX_DATA_PATH"] = str(self.sample_cache)
            os.environ["SYSTEM_MAPPING_PATH"] = str(
                self.repo_root / "scripts" / "system_mapping.json"
            )

            with TemporaryDirectory() as tmp_dir:
                output_path = Path(tmp_dir) / "feed.json"
                os.environ["FEED_OUTPUT_PATH"] = str(output_path)

                config = build_config()
                exit_code = generate_feed(config, dry_run=False)
                self.assertEqual(exit_code, 0)
                self.assertTrue(output_path.exists(), "Feed output file missing.")

                feed = json.loads(output_path.read_text())
                categories = {cat["title"] for cat in feed["categories"]}

                self.assertIn("Mega Drive", categories)
                self.assertIn("Commodore 64", categories)
                self.assertNotIn("Dreamcast", categories)
                self.assertNotIn("Switch (1Fichier)", categories)
        finally:
            os.environ.clear()
            os.environ.update(env_backup)


if __name__ == "__main__":
    unittest.main()
