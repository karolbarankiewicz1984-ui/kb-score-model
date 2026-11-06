import argparse
import json
from pathlib import Path
from github_models.event_markets import run

def main():
    parser = argparse.ArgumentParser()
    for key in ('queue', 'history', 'events', 'as-of', 'output'):
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    load = lambda path: json.loads(Path(path).read_text())
    result = run(load(args.queue), load(args.history), load(args.events), args.as_of)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('Event probabilities:', len(result['markets']), 'blockers:', len(result['blockers']))

if __name__ == '__main__':
    main()
