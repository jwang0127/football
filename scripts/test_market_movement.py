import json, tempfile, unittest
from pathlib import Path
from market_movement import load_market_movement

class MovementTests(unittest.TestCase):
    def test_opening_latest_and_probabilities(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); target = root / "data" / "odds_snapshots" / "20260815"; target.mkdir(parents=True)
            for i, home in enumerate((2.0, 1.7)):
                payload = {"capturedAt": f"2026-08-15T0{i}:00:00", "matches": [{"matchId": "1", "odds": {"had": {"home": str(home), "draw": "3.5", "away": "4.0"}, "hhad": {"home": "1.90", "draw": "3.40", "away": "3.80"}}}]}
                (target / f"20260815_0{i}.json").write_text(json.dumps(payload), encoding="utf-8")
            row = load_market_movement(root, "20260815")["1"]
            self.assertEqual(row["snapshotCount"], 2)
            self.assertLess(row["latest"]["had"]["home"], row["opening"]["had"]["home"])
            self.assertEqual(row["directionalSignal"], "home")
            self.assertIn("hhad", row["probabilityDelta"])
            self.assertIn(row["handicapSignal"], {"home", "away", "draw", "neutral"})

if __name__ == "__main__": unittest.main()
