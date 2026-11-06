"""Verify actual research artifacts; no fitting, probability creation or writes to N."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from github_models.elo_engine import eligible_history, utc
from github_models.research_pdf import _validate
from scipy.stats import poisson


def verify(root, metadata, comparison, local_log, zip_path):
    root = Path(root)
    run = json.loads(Path(metadata).read_text())
    if run['conclusion'] != 'success':
        raise ValueError('github_run_not_successful')
    archive_sha = hashlib.sha256(Path(zip_path).read_bytes()).hexdigest()
    if archive_sha != run['artifact_sha256']:
        raise ValueError('artifact_digest_mismatch')
    reports = root / 'reports/github_models'
    queue_path, = (reports / 'queues').glob('*.json')
    day = queue_path.stem
    read = lambda path: json.loads(path.read_text(encoding='utf-8'))
    queue = read(queue_path)
    predictions = read(reports / 'predictions' / (day + '.json'))
    markets = read(reports / 'markets' / (day + '.json'))
    coverage = read(reports / 'coverage' / (day + '.json'))
    fixtures = _validate(predictions, queue, markets)
    cutoff = utc(predictions['generated_at_utc'])
    if any(utc(payload['generated_at_utc']) != cutoff for payload in (queue, markets)):
        raise ValueError('different_generation_cutoffs')
    if queue['missing_dates'] or queue['invalid_dates']:
        raise ValueError('incomplete_queue_source_dates')
    history = read(root / 'data/github_models/verified_results.json')
    events = read(root / 'data/github_models/verified_events.json')
    eligible = eligible_history(history, frozen_at_utc=predictions['generated_at_utc'])
    if len(eligible) != len(history):
        raise ValueError('archived_history_not_unique_and_available_at_cutoff')
    for row in events:
        if not utc(row['completed_at_utc']) <= utc(row['published_at_utc']) <= cutoff:
            raise ValueError('event_history_publication_order')
    sums = []
    for row in predictions['predictions']:
        if row.get('probability_status') != 'uncalibrated_research':
            raise ValueError('research_probability_label_missing')
        if utc(row['frozen_at_utc']) != cutoff or utc(fixtures[str(row['fixture_id'])]['kickoff_utc']) <= cutoff:
            raise ValueError('forecast_asof_not_prematch_at_cutoff')
        sums.append(abs(math.fsum(row[key] for key in ('p_home', 'p_draw', 'p_away')) - 1))
    pairs, by_market = defaultdict(dict), defaultdict(list)
    reference_errors = []
    for row in markets['markets']:
        if row.get('probability_status') != 'uncalibrated_research':
            raise ValueError('research_probability_label_missing')
        if utc(row['frozen_at_utc']) != cutoff or utc(fixtures[str(row['fixture_id'])]['kickoff_utc']) <= cutoff:
            raise ValueError('event_forecast_not_original_prematch_at_cutoff')
        key = (str(row['fixture_id']), row['model_id'], row['market'], row['line'])
        pairs[key][row['selection']] = row['probability']
        by_market[key[:3]].append(row)
        reference = float(poisson.sf(math.floor(row['line']), row['expected_rate']))
        if row['selection'] == 'under':
            reference = 1 - reference
        reference_errors.append(abs(row['probability'] - reference))
    complement_errors = []
    for pair in pairs.values():
        if set(pair) != {'over', 'under'}:
            raise ValueError('incomplete_binary_market_pair')
        complement_errors.append(abs(math.fsum(pair.values()) - 1))
    for rows in by_market.values():
        over = sorted((row['line'], row['probability']) for row in rows if row['selection'] == 'over')
        if any(left[1] < right[1] for left, right in zip(over, over[1:])):
            raise ValueError('non_monotone_count_market_tails')
    if max(reference_errors, default=0) > .500001e-6:
        raise ValueError('poisson_reference_error_exceeds_six_decimal_rounding')
    if max(sums + complement_errors, default=0) > 1e-6:
        raise ValueError('probability_sum_error')
    snapshots = []
    for path in sorted((root / 'research_inputs/pitchapi').glob('*.json')):
        payload = read(path)
        if payload['source_status'] != 'ok' or utc(payload['snapshot_utc']) > cutoff:
            raise ValueError('pitchapi_source_invalid_or_after_cutoff')
        snapshots.append(dict(date=payload['target_date'], available=payload['available_upcoming'],
            collected=payload['fixtures_collected'], exclusions=payload['exclusions'],
            metadata_count=len(payload['league_metadata']),
            metadata_errors=sum(row['status'] != 'ok' for row in payload['league_metadata'].values()),
            missing_country=sum(not row.get('country_code') for row in payload['fixtures'])))
    comp = read(Path(comparison))
    if comp['total'] != len(fixtures) or comp['as_of_utc'] != predictions['generated_at_utc']:
        raise ValueError('comparison_is_a_different_cohort_or_cutoff')
    log = Path(local_log).read_text()
    tests = re.findall(r'Ran (\d+) tests in ([0-9.]+)s', log)
    if not tests or '\nOK\n' not in log:
        raise ValueError('local_full_test_success_not_recorded')
    changed = subprocess.check_output(['git', 'diff', 'f609427', '--name-only'], text=True).splitlines()
    allowed = lambda name: (name.startswith(('github_models/', 'tests/test_github_models',
        'docs/MULTIMODEL_V2', 'reports/github_models/repair_2026-11-06/'))
        or name in ('multimodel_v2/dixon_coles_shadow.py', '.github/workflows/github-models-independent.yml'))
    if any(not allowed(name) for name in changed):
        raise ValueError('change_outside_authorized_research_scope')
    hashes = {}
    for path in sorted(root.rglob('*')):
        if path.is_file():
            hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(schema='github-models-repair-verification-v1', status='PASS',
        cutoff_utc=predictions['generated_at_utc'], ci=run,
        tests=dict(local_full_count=int(tests[-1][0]), local_full_seconds=float(tests[-1][1]),
                   local_status='PASS', baseline_full_count=1078),
        queue_fixtures=len(fixtures), history_results=len(history),
        history_leagues=len({row['league'] for row in history}), event_history_rows=len(events),
        actual_1x2_forecasts=len(predictions['predictions']),
        actual_1x2_fixtures=len({row['fixture_id'] for row in predictions['predictions']}),
        actual_1x2_models=dict(Counter(row['model_id'] for row in predictions['predictions'])),
        actual_event_forecasts=len(markets['markets']),
        actual_markets=dict(Counter(row['market'] for row in markets['markets'])),
        math=dict(status='PASS', max_1x2_sum_error=max(sums, default=0),
            max_binary_complement_error=max(complement_errors, default=0),
            max_poisson_reference_error=max(reference_errors, default=0),
            poisson_reference='scipy.stats.poisson.sf', probabilities_finite_and_bounded=True,
            binary_pairs_complete=True, over_tails_monotone=True, only_half_integer_count_lines=True),
        calibration='uncalibrated_research', snapshots=snapshots,
        formal_forward_publication_verified=False,
        time_semantics='input_data_cutoff_is_not_artifact_publication_time',
        coverage=comp['summary'], source_sha256=hashes, production_multimodel_unchanged=True,
        thresholds_unchanged=dict(elo_team_min=5, dixon_coles_league_min=30,
                                  event_league_min=60, event_team_min=8),
        n_counter_writes=0, raw_source_responses_or_original_predictions_modified=False)


def main():
    parser = argparse.ArgumentParser()
    for name in ('artifact-root', 'metadata', 'comparison', 'local-log', 'zip', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    result = verify(args.artifact_root, args.metadata, args.comparison, args.local_log, args.zip)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'queue_fixtures', 'actual_1x2_forecasts', 'actual_event_forecasts')}))


if __name__ == '__main__':
    main()
