"""Official bookmaker rules are not vendor source-equivalence proofs."""
import unittest

from github_models.disciplinary_rules import (
    SOURCE_REQUIREMENTS, review_capabilities, review_football_data_schema,
    total_cards_from_verified_trajectories,
)
from github_models.market_rule_gate import audit
from github_models.unified_output import market_label

def card(yellow_count=0,straight_red=False,second_yellow_dismissal=False,
         on_pitch_at_card=True,after_final_whistle=False,
         in_halftime=False,resumed_second_half=True,official_event_verified=True):
    return locals()

class DisciplinaryValidation(unittest.TestCase):
    def test_fd_aggregates_cannot_prove_referee_advantage_or_booking_semantics(self):
        r=review_football_data_schema()
        self.assertEqual(set(r),{"fouls","cards"})
        for x in r.values():
            self.assertTrue(x["missing_required_fields"])
            self.assertFalse(x["source_event_schema_compatible"])
            self.assertFalse(x["automatic_market_promotion"])
            self.assertFalse(x["bookmaker_payout_verified"])
            self.assertFalse(x["booking_units_equivalent_to_yellow_cards"])

    def test_even_complete_official_opta_fields_do_not_prove_provider_market_payout(self):
        for market,fields in SOURCE_REQUIREMENTS.items():
            out=review_capabilities(
                market=market,field_names=list(fields),
                source_provider="OPTA-official-event-data",
                provider_market_identity_verified=True,
                bookmaker_payout_verified=False)
            self.assertTrue(out["source_event_schema_compatible"])
            self.assertFalse(out["automatic_market_promotion"])
            self.assertFalse(out["official_superbet_payout_confirmed_by_this_gate"])

    def test_player_card_trajectories_and_exclusions(self):
        seq=[card(yellow_count=1),card(straight_red=True),
             card(yellow_count=2,second_yellow_dismissal=True)]
        self.assertEqual(total_cards_from_verified_trajectories(seq),6)
        excluded=[card(yellow_count=1,on_pitch_at_card=False),
                  card(straight_red=True,after_final_whistle=True),
                  card(yellow_count=1,in_halftime=True,resumed_second_half=False)]
        self.assertEqual(total_cards_from_verified_trajectories(excluded),0)

    def test_unverified_or_contradictory_cards_are_rejected(self):
        with self.assertRaisesRegex(ValueError,"unverified_player_event"):
            total_cards_from_verified_trajectories([card(official_event_verified=False)])
        with self.assertRaisesRegex(ValueError,"conflicting_red_card_events"):
            total_cards_from_verified_trajectories([card(yellow_count=1,second_yellow_dismissal=True)])
        with self.assertRaisesRegex(ValueError,"incomplete_player_event_trajectory"):
            total_cards_from_verified_trajectories([{"yellow_count":1}])

    def test_bookings_snapshot_not_promoted_despite_official_rule_text(self):
        quote={"bookmaker":"superbet.pl","market_name":"Bookings - Over Under Full Time",
               "market_type":"totals-bookings","period":"fulltime",
               "outcome_name":"Over","handicap":4.5,"player_prop":False,
               "player_id":"0","odds":1.35,"market_id":"bookings"}
        c={"bookmakers":["superbet.pl"],"snapshots":[{
            "provider":"oddspapi-v4",
            "captured_at_utc":"2026-11-23T14:00:00Z",
            "kickoff_utc":"2026-11-23T21:00:00Z",
            "quotes":[quote]}]}
        out=audit(c)
        self.assertEqual(out["automatically_promoted_markets"],[])
        self.assertEqual(out["family_counts"]["bookings_or_cards"],1)
        self.assertEqual(out["bookings_unit_status"],"provider_confirmation_missing_oddsPapi_v4")
        self.assertIn("official_superbet_rules",out)
        self.assertFalse(out["disciplinary_source_validation"]["cards"]["source_event_schema_compatible"])

    def test_double_chance_pdf_market_identity_is_strict(self):
        self.assertIn("1X",market_label({"market":"double_chance","selection":"1X","line":None}))
        self.assertIn("X2",market_label({"market":"double_chance","selection":"X2","line":None}))
        self.assertIn("12",market_label({"market":"double_chance","selection":"12","line":None}))
        with self.assertRaisesRegex(ValueError,"invalid_double_chance_identity"):
            market_label({"market":"double_chance","selection":"1X","line":1.5})

if __name__ == "__main__":
    unittest.main()
