import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from api_market_presentation import practical_shortlist


def candidate(fixture, score, odd, number):
    return {
        "fixture_id": fixture, "final_assessment_pct": score,
        "direction": "under", "selection": str(number),
        "market_data": {"quotes": [{"bookmaker": "Any API source", "under_odd": odd}]},
    }


class MainListTests(unittest.TestCase):
    def test_odds_score_and_per_match_limit(self):
        positions = [candidate(1, 95-i, 1.21, i) for i in range(5)]
        positions += [candidate(2, 90, 1.19, 6), candidate(3, 66, 1.8, 7)]
        positions += [candidate(4, 80, 1.20, 8)]
        result = practical_shortlist(positions)
        self.assertEqual(len(result), 4)
        self.assertEqual(sum(x["fixture_id"] == 1 for x in result), 3)
        self.assertTrue(any(x["fixture_id"] == 4 for x in result))
        self.assertEqual(len(positions), 8)

    def test_no_total_limit(self):
        positions = [candidate(i, 70, 1.25, i) for i in range(15)]
        self.assertEqual(len(practical_shortlist(positions)), 15)


if __name__ == "__main__":
    unittest.main()
