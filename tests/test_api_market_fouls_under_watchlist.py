"""Regression checks for the separate, display-only fouls UNDER odds band."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from api_market_presentation import fouls_under_watchlist


def candidate(fid, line, score, odd, *, direction="under", team=1,
              timestamp="2026-10-22T09:00:00Z", market="fouls"):
    return {
        "fixture_id": fid, "team_id": team, "market": market,
        "market_scope": "team", "direction": direction,
        "line": line, "final_assessment_pct": score,
        "home": "Gospodarze", "away": "Goście",
        "kickoff": "2026-10-22T21:00:00+02:00",
        "selection": f"Gospodarze: poniżej {line:.1f} — faule drużyny",
        "market_data": {"quotes": [{
            "bookmaker": "RecordedBook", f"{direction}_odd": odd,
            "provider_updated_at": timestamp
        }]},
    }


class FoulsUnderWatchlistTests(unittest.TestCase):
    def test_exact_range_and_direction_with_independent_score_gate(self):
        rows = [
            candidate(1, 14.5, 70, 1.50),
            candidate(1, 13.5, 71, 1.80),  # same match/team/family: higher score wins
            candidate(2, 11.5, 55, 2.00),  # below 67 is still observable
            candidate(3, 12.5, 88, 2.01),
            candidate(4, 12.5, 90, 1.49),
            candidate(5, 12.5, 92, 1.70, direction="over"),
            candidate(6, 12.5, 91, 1.70, market="yellow"),
            candidate(7, 12.5, 99, 1.60, timestamp=None),
            candidate(8, 12.5, 99, 1.60, timestamp="2026-10-22T20:00:00Z"),
        ]
        payload = {"date": "2026-10-22", "background_candidates": rows,
                   "top_positions": [rows[0]]}
        original = copy.deepcopy(payload)
        result = fouls_under_watchlist(payload)
        self.assertEqual(result["total"], 2)
        self.assertEqual([r["item"]["fixture_id"] for r in result["rows"]], [1, 2])
        self.assertEqual(result["rows"][0]["quote"]["selected_odd"], 1.80)
        self.assertEqual(result["rows"][1]["score"], 55)
        self.assertEqual(payload, original)

    def test_no_background_fallback_and_empty(self):
        x = candidate(7, 20.5, 68, 1.72)
        self.assertEqual(fouls_under_watchlist({
            "date": "2026-10-22", "top_positions": [x]
        })["total"], 1)
        self.assertEqual(fouls_under_watchlist({
            "date": "2026-10-21", "top_positions": [x]
        })["total"], 0)


if __name__ == "__main__":
    unittest.main()
