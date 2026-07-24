import json
import tempfile
import unittest
from pathlib import Path

from generate_date_pages import latest_competition_review
from generate_homepage import load_daily_rows, render
from refresh_site_layout import refresh
from update_review_and_future import update_review_and_future


class HomepageWorkflowTests(unittest.TestCase):
    def test_daily_pages_are_sorted_newest_first(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            for compact in ("20260720", "20260722", "20260721"):
                (root / compact).mkdir()
                (root / compact / "index.html").write_text("<html></html>", encoding="utf-8")
                payload = {"matches": [{"league": "测试联赛"}]}
                (root / "data" / f"predictions_{compact}.json").write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
                )
            self.assertEqual([row["date"] for row in load_daily_rows(root)], ["20260722", "20260721", "20260720"])
            page = render(root)
            self.assertIn('class="date-row"', page)
            self.assertLess(page.index("2026-07-22"), page.index("2026-07-21"))

    def test_review_selection_is_strictly_before_prediction_date(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            for compact in ("20260718", "20260719", "20260720"):
                (data / f"review_{compact}_competitions.json").write_text(
                    json.dumps({"reviewDate": compact}), encoding="utf-8"
                )
            self.assertEqual(latest_competition_review("20260720", data)["reviewDate"], "20260719")

    def test_layout_refresh_is_idempotent_and_removes_review_links(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "assets").mkdir()
            (root / "assets" / "site.css").write_text("body{}", encoding="utf-8")
            page_dir = root / "20260720"
            page_dir.mkdir()
            page = page_dir / "index.html"
            page.write_text('<html><head></head><body><a href="review.html">复盘</a></body></html>', encoding="utf-8")
            self.assertEqual(len(refresh(root)), 1)
            updated = page.read_text(encoding="utf-8")
            self.assertIn("../assets/site.css", updated)
            self.assertNotIn("review.html", updated)
            self.assertEqual(refresh(root), [])

    def test_future_update_skips_only_missing_source_days(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            result = update_review_and_future("20260720", root)
            self.assertEqual(result["generated"], [])
            self.assertEqual(len(result["skipped"]), 3)
            self.assertTrue((root / "index.html").exists())


if __name__ == "__main__":
    unittest.main()
