"""Read-only PitchAPI historical goal-opportunity review for API Market selections.

Never changes scores, weights, odds, ranking, published picks, or N counters.
The signal is UNCALIBRATED background context, not a probability.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
from pathlib import Path

try:
    from tools.pitchapi_prematch_context import lookup_context
except ModuleNotFoundError as exc:
    if exc.name != 'tools':
        raise
    from pitchapi_prematch_context import lookup_context


def parse_utc(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (TypeError, ValueError):
        return None


def load_snapshot(day: str, root: Path = Path('.')):
    """Never fetch network data: missing or invalid report disables overlay."""
    path = root / 'data/pitchapi/prematch' / f'{day}.json'
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if (not isinstance(payload, dict)
            or payload.get('schema') != 'pitchapi-prematch-context-v1'
            or payload.get('target_date') != day):
        return None
    return payload


def review_position(position, snapshot, *, minimum=4, margin=0.75):
    """Direction of historic xG opportunity index versus quoted goal line.

    Descriptive comparison only: index is not modeled expectation of goals.
    Do not derive calibrated probabilities from this heuristic.
    """
    if position.get('market') != 'team_goals':
        return None  # Do NOT extrapolate to corners, fouls, cards or saves.
    if not snapshot or snapshot.get('schema') != 'pitchapi-prematch-context-v1':
        return {'status':'no_data', 'label':'PitchAPI: brak danych historycznych.'}
    # API Market production records use kickoff_utc. Older records used kickoff.
    # Accept either without changing the original selection or its rating.
    kickoff_value = position.get('kickoff_utc') or position.get('kickoff')
    kickoff, captured = parse_utc(kickoff_value), parse_utc(snapshot.get('snapshot_utc'))
    if kickoff is None or captured is None or captured >= kickoff:
        return {'status':'no_data','label':'PitchAPI: brak danych sprzed rozpoczęcia meczu.'}
    match = lookup_context(snapshot, position.get('home'), position.get('away'),
                           position.get('competition'), kickoff_value)
    if match is None:
        return {'status':'no_data','label':'PitchAPI: brak jednoznacznie dopasowanego meczu.'}
    home, away = match.get('home_recent') or {}, match.get('away_recent') or {}
    for sample in (home, away):
        if sample.get('complete_samples', 0) < minimum:
            return {'status':'insufficient','label':'PitchAPI: za mało wcześniejszych meczów.'}
        if not all(type(sample.get(key)) in (int, float) and sample[key] >= 0
                   for key in ('mean_xg_for', 'mean_xg_against')):
            return {'status':'insufficient','label':'PitchAPI: niekompletne dane o okazjach.'}
        if not sample.get('samples'):
            return {'status':'insufficient','label':'PitchAPI: brak dat meczów historycznych.'}
        if any((parse_utc(s.get('kickoff_utc')) is None or
                parse_utc(s.get('kickoff_utc')) >= captured or
                parse_utc(s.get('kickoff_utc')) >= kickoff) for s in sample['samples']):
            return {'status':'no_data','label':'PitchAPI: dane historyczne wymagają kontroli dat.'}
    direction = position.get('direction')
    line = position.get('line')
    if direction not in ('over', 'under') or type(line) not in (int, float):
        return {'status':'no_data','label':'PitchAPI: linia lub kierunek nierozpoznane.'}
    home_index = (home['mean_xg_for'] + away['mean_xg_against']) / 2
    away_index = (away['mean_xg_for'] + home['mean_xg_against']) / 2
    if position.get('market_scope') == 'match':
        index, subject = home_index + away_index, 'całego meczu'
    elif position.get('team_side') == 'home':
        index, subject = home_index, 'gospodarzy'
    elif position.get('team_side') == 'away':
        index, subject = away_index, 'gości'
    else:
        return {'status':'no_data','label':'PitchAPI: nieustalona drużyna.'}
    directional = (index - line) if direction == 'over' else (line - index)
    if directional >= margin:
        status, phrase = 'favors', 'historia okazji sprzyja temu typowi'
    elif directional <= -margin:
        status, phrase = 'cautions', 'uwaga: historia okazji przemawia przeciw temu typowi'
    else:
        status, phrase = 'mixed', 'historia okazji nie daje wyraźnego sygnału'
    return {
        'status': status,
        'opportunity_index': round(index, 2),
        'line': line,
        'sample_home': home['complete_samples'],
        'sample_away': away['complete_samples'],
        'label': (f'PitchAPI: {phrase} (wskaźnik jakości okazji {subject} {index:.2f}, '
                  f'linia {line:g}, historia {home["complete_samples"]}/{away["complete_samples"]} spotkań). '
                  'Sygnał poglądowy, nie prognoza ani prawdopodobieństwo.'),
    }
