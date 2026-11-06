"""Research-only metrics for settled, immutable A/B/C forecasts."""
import math

def metrics(rows):
    valid = [r for r in rows if r.get('status') == 'settled']
    n = len(valid)
    return {
        'total': len(rows), 'settled': n, 'unresolved': len(rows)-n,
        'unique_fixtures': len({str(r['fixture_id']) for r in valid}),
        'hits': sum(bool(r['hit']) for r in valid),
        'hit_rate': sum(bool(r['hit']) for r in valid)/n if n else None,
        'brier': sum((r['probability']-int(r['hit']))**2 for r in valid)/n if n else None,
        'log_loss': sum(-math.log(max(r['probability'] if r['hit'] else 1-r['probability'],1e-15)) for r in valid)/n if n else None,
    }
