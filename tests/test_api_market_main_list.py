import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from api_market_presentation import practical_shortlist


def candidate(fixture, score, odd, number):
    return {
        "fixture_id": fixture, "team_id": fixture, "market": "corners",
        "market_scope": "team", "direction": "under", "line": number + 0.5,
        "final_assessment_pct": score,
        "selection": str(number),
        "market_data": {"quotes": [{"bookmaker": "Any API source", "under_odd": odd}]},
    }


class MainListTests(unittest.TestCase):
    def test_odds_score_and_per_match_limit(self):
        positions = [candidate(1, 95-i, 1.21, i) for i in range(5)]
        positions += [candidate(2, 90, 1.19, 6), candidate(3, 66, 1.8, 7)]
        positions += [candidate(4, 80, 1.20, 8)]
        result = practical_shortlist(positions)
        self.assertEqual(len(result), 2)
        self.assertEqual(sum(x["fixture_id"] == 1 for x in result), 1)
        self.assertTrue(any(x["fixture_id"] == 4 for x in result))
        self.assertEqual(len(positions), 8)

    def test_different_market_or_direction_remains_eligible(self):
        a = candidate(1, 85, 1.25, 5)
        b = candidate(1, 84, 1.30, 6)
        b["market"] = "yellow_cards"
        c = candidate(1, 83, 1.35, 7)
        c["direction"] = "over"
        c["market_data"]["quotes"][0]["over_odd"] = 1.35
        self.assertEqual(len(practical_shortlist([a, b, c])), 3)

    def test_no_total_limit(self):
        positions = [candidate(i, 70, 1.25, i) for i in range(15)]
        self.assertEqual(len(practical_shortlist(positions)), 15)


if __name__ == "__main__":
    unittest.main()
