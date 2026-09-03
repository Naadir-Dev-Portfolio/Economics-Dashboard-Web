"""Observation validation, calendar-based statistics and freshness policy."""
from bisect import bisect_right
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from math import isfinite
from statistics import median
import json
import os
import tempfile

UTC = timezone.utc
DAY_MS = 86_400_000
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
SCHEMA_VERSION = 2


def write_json(path, payload, indent=None):
    """Replace complete JSON atomically; never publish a partially written file."""
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     prefix=path.name + '.', suffix='.tmp', delete=False) as handle:
        temporary = handle.name
        try:
            json.dump(payload, handle, ensure_ascii=False, allow_nan=False,
                      indent=indent, separators=None if indent else (',', ':'))
            handle.flush()
            os.fsync(handle.fileno())
        except Exception:
            handle.close()
            os.unlink(temporary)
            raise
    os.replace(temporary, path)


def from_ms(ms):
    return EPOCH + timedelta(milliseconds=ms)


def to_ms(value):
    return int((datetime.fromisoformat(value).replace(tzinfo=UTC) - EPOCH).total_seconds() * 1000)


def validate_points(points, now=None):
    """Reject corrupt responses before they can replace a good local series."""
    today = (now or datetime.now(UTC)).date()
    result = {}
    for point in points:
        if len(point) != 2:
            raise ValueError('Observation must contain a timestamp and a value')
        ts, value = point
        if isinstance(ts, bool) or isinstance(value, bool):
            raise ValueError('Boolean observation')
        ts, value = int(ts), float(value)
        if not isfinite(value):
            raise ValueError('Non-finite observation')
        if from_ms(ts).date() > today:
            raise ValueError(f'Future observation: {from_ms(ts).date()}')
        if ts in result and result[ts] != value:
            raise ValueError('Conflicting duplicate observations')
        result[ts] = value
    if not result:
        raise ValueError('No observations')
    return [[ts, result[ts]] for ts in sorted(result)]


def frequency_of(data):
    if len(data) < 2:
        return 'm'
    tail = data[-60:]
    gap = median((b[0] - a[0]) / DAY_MS for a, b in zip(tail, tail[1:]))
    return 'd' if gap < 5 else 'w' if gap < 15 else 'm' if gap < 45 else 'q' if gap < 120 else 'a'


def months_before(dt, count):
    offset = dt.year * 12 + dt.month - 1 - count
    year, month = divmod(offset, 12)
    return dt.replace(year=year, month=month + 1, day=min(dt.day, monthrange(year, month + 1)[1]))


def yoy(data):
    # Match calendar periods, not row offsets: missing months must not shift YoY.
    values = {(from_ms(ts).year, from_ms(ts).month): v for ts, v in data}
    result = []
    for ts, value in data:
        dt = from_ms(ts)
        prior = values.get((dt.year - 1, dt.month))
        if prior not in (None, 0):
            result.append([ts, round((value / prior - 1) * 100, 4)])
    return result


def compute_stats(data, frequency=None):
    if not data:
        return {}
    frequency = frequency or frequency_of(data)
    latest_ts, latest = data[-1]
    last_dt = from_ms(latest_ts)
    dates = [p[0] for p in data]
    values = [p[1] for p in data]
    stats = {'last_value': round(latest, 4), 'last_date': last_dt.date().isoformat(), 'n_points': len(data)}
    for months, key in [(1, '1m'), (3, '3m'), (12, '1y'), (60, '5y')]:
        target = months_before(last_dt, months)
        index = bisect_right(dates, int((target - EPOCH).total_seconds() * 1000)) - 1
        valid = index >= 0 and (target - from_ms(dates[index])).days <= {'d': 7, 'w': 14, 'm': 35, 'q': 100, 'a': 370}[frequency]
        valid = valid and months >= {'d': 0, 'w': 0, 'm': 1, 'q': 3, 'a': 12}[frequency]
        prior = values[index] if valid else None
        stats[f'chg_{key}_pct'] = round((latest / prior - 1) * 100, 3) if prior not in (None, 0) else None
        stats[f'chg_{key}_pp'] = round(latest - prior, 3) if prior is not None else None
    stats['chg_max_pct'] = round((latest / values[0] - 1) * 100, 2) if values[0] else None
    for name, fn in [('min', min), ('max', max)]:
        value = fn(values)
        stats[name] = round(value, 4)
        stats[f'{name}_date'] = from_ms(dates[values.index(value)]).date().isoformat()
    return stats


def period_label(data, frequency):
    dt = from_ms(data[-1][0])
    if frequency == 'q':
        return f'Q{(dt.month - 1) // 3 + 1} {dt.year}'
    if frequency == 'm':
        return dt.strftime('%b %Y')
    if frequency == 'a':
        return str(dt.year)
    return dt.strftime('%d %b %Y').lstrip('0')


def freshness(series, config=None, now=None):
    config = config or {}
    now = now or datetime.now(UTC)
    if config.get('archived') or series.get('archived'):
        return 'archived'
    stats = series.get('stats') or {}
    if not stats.get('last_date'):
        return 'missing'
    observed = datetime.fromisoformat(stats['last_date']).date()
    age = (now.date() - observed).days
    if age < 0:
        return 'invalid'
    freq = series.get('frequency', 'm')
    if freq in ('m', 'q', 'a'):
        end_month = (observed.month - 1) // 3 * 3 + 3 if freq == 'q' else 12 if freq == 'a' else observed.month
        period_end = observed.replace(month=end_month, day=monthrange(observed.year, end_month)[1])
        age = max(0, (now.date() - period_end).days)
    limit = config.get('max_age_days', series.get('max_age_days', {'d': 7, 'w': 21, 'm': 100, 'q': 230, 'a': 800}.get(freq, 100)))
    if age > limit:
        return 'stale'
    release = series.get('next_release')
    if release:
        try:
            if (now.date() - datetime.fromisoformat(release).date()).days > 2:
                return 'stale'
        except ValueError:
            pass
    return 'current'
