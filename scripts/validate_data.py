"""Reject corrupt artifacts before publishing and report degraded source health."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import math
import os

from data_quality import SCHEMA_VERSION, from_ms, validate_points
from series_config import SECTIONS

DATA = Path(__file__).resolve().parent.parent / 'data'


def validate(root=DATA):
    errors = []
    for section, spec in SECTIONS.items():
        try:
            payload = json.loads((root / (section + '.json')).read_text(encoding='utf-8'))
            for config in spec['series']:
                item = payload.get('series', {}).get(config['id'])
                if not item:
                    errors.append(f"{section}/{config['id']}: missing series")
                    continue
                points = validate_points(item['data'])
                stats = item['stats']
                if points != item['data']:
                    raise ValueError(f"{config['id']}: unsorted or duplicate data")
                if stats['n_points'] != len(points) or stats['last_date'] != from_ms(points[-1][0]).date().isoformat():
                    raise ValueError(f"{config['id']}: statistics disagree with observations")
                if not math.isclose(stats['last_value'], points[-1][1], abs_tol=0.000051):
                    raise ValueError(f"{config['id']}: incorrect last value")
                if item.get('schema_version') != SCHEMA_VERSION or item.get('unit') != config.get('unit'):
                    raise ValueError(f"{config['id']}: outdated schema or unit")
                if item.get('name') != config['name'] or item.get('history_version', 1) != config.get('history_version', 1):
                    raise ValueError(f"{config['id']}: data does not match the configured definition")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f'{section}: {exc}')
    try:
        calendar = json.loads((root / 'calendar.json').read_text(encoding='utf-8'))
        if calendar['meta'].get('schema_version') != SCHEMA_VERSION:
            raise ValueError('Unverified legacy calendar')
        seen = set()
        for event in calendar['events']:
            if event['id'] in seen:
                raise ValueError('Duplicate calendar event')
            seen.add(event['id'])
            if event.get('status') not in ('confirmed', 'provisional') or not event.get('verified_at'):
                raise ValueError('Calendar entry has not been verified')
            if datetime.fromisoformat(event['datetime']).tzinfo is None:
                raise ValueError('Calendar entry has no timezone')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f'calendar: {exc}')
    return errors


def report(root=DATA):
    health = json.loads((root / 'health.json').read_text(encoding='utf-8'))
    lines = ['## Data quality', '', '| Source | Current / Expected | Status |', '| --- | --- | --- |']
    action_needed = []
    issue_lines = []
    for source in health['sources']:
        if source.get('runtime'):
            continue
        lines.append(f"| {source['name']} | {source.get('delivered', 0)} / {source.get('expected', 0)} | {source.get('status')} |")
        for issue in source.get('issues', []):
            message = f"{issue['name']}: {issue['reason']} ({issue.get('period') or 'no observation'})"
            issue_lines.append(f"- {message}")
            if issue['reason'] != 'verified cache':
                action_needed.append(message)
        if source.get('status') == 'error':
            action_needed.append(source['name'] + ': source unavailable')
    output = '\n'.join(lines + (['', '### Source notes', ''] + issue_lines if issue_lines else [])) + '\n'
    print(output)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as handle:
            handle.write(output)
    return action_needed


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    problems = report() if args.report else validate()
    for problem in problems:
        print('::error::' + problem)
    if not args.report and not problems:
        print('Validated all observations, statistics and published calendar entries.')
    raise SystemExit(1 if problems else 0)
