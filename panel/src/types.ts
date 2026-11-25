export const SECTIONS = ['FIXTURES','FORECASTS','ODDS','RESULTS','AUDIT','CALIBRATION_READINESS','CALIBRATION_EXPERIMENTS','MODEL_VERSIONS','SOURCE_HEALTH'] as const;
export type Section = typeof SECTIONS[number];
export type Manifest = {schema:string; day:string; generated_at_utc:string; forecast_cutoff_utc:string; audit_as_of_utc:string; files:Record<string,{bytes:number;sha256:string}>; historical_snapshot:true; publication:string};
export type Fixture = {fixture_id:string;home:string;away:string;league:string;kickoff_utc:string};
export type Quote = {price:number;captured_at_utc:string;bookmaker:string;source_market_id:string|null;source_outcome_id:string|null;source_odds_fixture_id:string|null};
export type LinkRow = {forecast_identity:unknown[];fixture_id:string;market:string;selection:string;line:number|null;model:string;variant:string|null;lane:'ABC'|'SHADOW';probability:number;probability_status:string;quality_score:null;quote:Quote|null;quote_status:string;top_eligible:false};
export type Readiness = {distinct_fixtures_used_for_gate:number;fixtures_remaining_to_100_review:number;holdout_evidence_available:boolean;calibration_authorized:false;abc_distinct_settled_fixtures:number;shadow_distinct_settled_fixtures:number;abc_settled_quotes:number;shadow_settled_quotes:number;exact_cross_model_fixture_union_verified:boolean};
export type Snapshot = {manifest:Manifest;sections:Record<Section,unknown>;fixtures:Fixture[];rows:LinkRow[];readiness:Readiness;importedAt:string};
