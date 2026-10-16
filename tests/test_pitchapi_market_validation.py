"""PitchAPI must never change original API Market selections or scores."""
import json
import tempfile
import unittest
from pathlib import Path

from tools.pitchapi_market_validation import review_position, load_snapshot


def snapshot(home_for=2.2, away_conceded=2.4, n=5):
    def team(xg, xga):
        return {'mean_xg_for':xg,'mean_xg_against':xga,'complete_samples':n,
                'samples':[{'kickoff_utc':'2026-10-11T17:00:00Z'} for _ in range(n)]}
    return {'schema':'pitchapi-prematch-context-v1','target_date':'2026-10-16',
            'snapshot_utc':'2026-10-15T18:00:00Z',
            'fixtures':[{'home':'Roma','away':'Real Madrid','league':'Champions League',
                         'kickoff_utc':'2026-10-16T19:00:00Z',
                         'home_recent':team(home_for,1.0),
                         'away_recent':team(0.9,away_conceded)}]}

def bet(**kw):
    p={'fixture_id':123,'home':'Roma','away':'Real Madrid',
       'competition':'UEFA Champions League','kickoff':'2026-10-16T19:00:00Z',
       'market':'team_goals','market_scope':'team','team_side':'home',
       'direction':'over','line':1.5,'final_assessment_pct':73.0}
    return dict(p,**kw)

class PitchMarketTests(unittest.TestCase):
    def test_goal_over_favors(self):
        self.assertEqual(review_position(bet(),snapshot())['status'],'favors')
    def test_under_cautions(self):
        self.assertEqual(review_position(bet(direction='under'),snapshot())['status'],'cautions')
    def test_total_goals_review(self):
        r=review_position(bet(market_scope='match',line=2.5),snapshot())
        self.assertIsNotNone(r['opportunity_index'])
    def test_production_utc_kickoff_field_is_reviewed(self):
        # The published API Market renderer receives kickoff_utc, not kickoff.
        position = bet()
        position['kickoff_utc'] = position.pop('kickoff')
        r = review_position(position, snapshot())
        self.assertEqual(r['status'], 'favors')
        self.assertEqual(r['opportunity_index'], 2.3)

    def test_production_utc_kickoff_never_accepts_postmatch_snapshot(self):
        position = bet()
        position['kickoff_utc'] = position.pop('kickoff')
        context = snapshot()
        context['snapshot_utc'] = '2026-10-16T20:00:00Z'
        self.assertEqual(review_position(position, context)['status'], 'no_data')

    def test_no_cards_corners_fouls_or_shots(self):
        for market in ('yellow','corners','fouls','shots','shots_on_goal'):
            self.assertIsNone(review_position(bet(market=market),snapshot()))
    def test_insufficient_sample(self):
        self.assertEqual(review_position(bet(),snapshot(n=2))['status'],'insufficient')
    def test_after_kickoff_cannot_validate(self):
        s=snapshot()
        s['snapshot_utc']='2026-10-16T21:00:00Z'
        self.assertEqual(review_position(bet(),s)['status'],'no_data')
    def test_historical_future_leakage_fails(self):
        s=snapshot()
        s['fixtures'][0]['home_recent']['samples'][0]['kickoff_utc']='2026-10-16T20:00:00Z'
        self.assertEqual(review_position(bet(),s)['status'],'no_data')
    def test_no_ambiguous_match(self):
        s=snapshot()
        s['fixtures'].append(dict(s['fixtures'][0]))
        self.assertEqual(review_position(bet(),s)['status'],'no_data')
    def test_no_scoring_mutations(self):
        p=bet()
        before=json.dumps(p,sort_keys=True)
        review_position(p,snapshot())
        self.assertEqual(json.dumps(p,sort_keys=True),before)
    def test_no_data_not_zero(self):
        self.assertEqual(review_position(bet(),None)['status'],'no_data')
    def test_snapshot_schema_and_date(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'data/pitchapi/prematch/2026-10-16.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(snapshot()),encoding='utf-8')
            self.assertIsNotNone(load_snapshot('2026-10-16',Path(td)))
            self.assertIsNone(load_snapshot('2026-10-17',Path(td)))

if __name__ == '__main__':
    unittest.main()
