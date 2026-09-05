"""Choose a refresh mode, including health-aware catch-up schedules."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


UTC = timezone.utc
HOURLY_SCHEDULE = '7 * * * *'
CATCH_UP_SCHEDULE = '23 8,20 * * *'
MAX_FULL_AGE_HOURS = 8


def load_manifest(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def full_refresh_needed(manifest: dict, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    try:
        generated = datetime.fromisoformat(str(manifest['generated_at']).replace('Z', '+00:00'))
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=UTC)
        age_hours = (now - generated.astimezone(UTC)).total_seconds() / 3600
    except (KeyError, TypeError, ValueError):
        return True
    totals = manifest.get('totals')
    if totals is None:
        totals = {}
    if not isinstance(totals, dict):
        return True
    try:
        unhealthy = int(totals.get('fail', 0) or 0) > 0 or int(totals.get('stale', 0) or 0) > 0
    except (TypeError, ValueError):
        return True
    return age_hours < 0 or age_hours > MAX_FULL_AGE_HOURS or unhealthy


def decide_mode(event_name: str, schedule: str, dispatch_mode: str, manifest: dict,
                now: datetime | None = None) -> str:
    if event_name == 'workflow_dispatch':
        return dispatch_mode if dispatch_mode in {'all', 'data', 'news'} else 'all'
    if event_name == 'schedule' and schedule == HOURLY_SCHEDULE:
        return 'news'
    if event_name == 'schedule' and schedule == CATCH_UP_SCHEDULE:
        return 'all' if full_refresh_needed(manifest, now) else 'news'
    return 'all'


def main() -> str:
    manifest = load_manifest(Path(__file__).resolve().parents[1] / 'data' / 'manifest.json')
    mode = decide_mode(os.environ.get('EVENT_NAME', ''), os.environ.get('EVENT_SCHEDULE', ''),
                       os.environ.get('DISPATCH_MODE', ''), manifest)
    line = f'mode={mode}'
    output = os.environ.get('GITHUB_OUTPUT')
    if output:
        with Path(output).open('a', encoding='utf-8') as stream:
            stream.write(line + '\n')
    print(line)
    return mode


if __name__ == '__main__':
    main()
