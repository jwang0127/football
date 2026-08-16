import unittest

from fetch_match_evidence import event_row, normal


class EvidenceCollectorTests(unittest.TestCase):
    def test_normal_removes_punctuation_without_losing_cjk(self):
        self.assertEqual(normal("FC Tokyo / 东京"), "fctokyo东京")

    def test_event_row_keeps_completed_score_and_source(self):
        event = {
            "id": "42",
            "date": "2026-08-16T10:00:00Z",
            "status": {"type": {"completed": True, "name": "STATUS_FINAL"}},
            "competitions": [{"venue": {"fullName": "Test Stadium"}, "competitors": [
                {"homeAway": "home", "score": "2", "team": {"displayName": "Home"}},
                {"homeAway": "away", "score": "1", "team": {"displayName": "Away"}},
            ]}],
        }
        row = event_row(event, "https://example.test/scoreboard")
        self.assertEqual(row["result"], {"homeGoals": 2, "awayGoals": 1})
        self.assertEqual(row["venue"]["fullName"], "Test Stadium")
        self.assertEqual(row["sourceUrl"], "https://example.test/scoreboard")


if __name__ == "__main__":
    unittest.main()
