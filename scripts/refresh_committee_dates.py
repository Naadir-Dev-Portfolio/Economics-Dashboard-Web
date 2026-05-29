#!/usr/bin/env python3
"""
Annual maintenance helper — refresh the hand-curated BoE MPC and ECB
Governing Council date lists in fetch_calendar.py.

Run this once a year (usually December) after the central banks publish
their next-year schedule. Triggered by the staleness banner on the dashboard.

What it does
------------
1. Opens both schedule pages in your browser (so you don't have to remember
   the URLs).
2. You copy-paste the dates from each page into the prompt. The script
   extracts every YYYY-MM-DD or DD Month YYYY style date from your input,
   so you can paste raw text and not worry about format.
3. Rewrites the BOE_MPC_HARDCODED and ECB_HARDCODED constants in
   fetch_calendar.py with the new dates.
4. Prints the git commands to commit + push.

Usage
-----
    python scripts/refresh_committee_dates.py

Then follow the on-screen prompts. Hit Enter on a blank line to skip a
source (e.g. if you only need to refresh BoE).
"""

from __future__ import annotations

import re
import sys
import webbrowser
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "fetch_calendar.py"

BOE_URL = "https://www.bankofengland.co.uk/monetary-policy/decisions-and-minutes"
ECB_URL = "https://www.ecb.europa.eu/press/calendars/mgcgc/"

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

ISO_RE      = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
DM_RE       = re.compile(r"\b(\d{1,2})[\s-]*(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[\s,-]+(20\d{2})\b", re.I)
MD_RE       = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[\s-]+(\d{1,2})[\s,-]+(20\d{2})\b", re.I)
SLASH_RE    = re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b")


def extract_dates(raw: str) -> list[str]:
    """Pull ISO dates out of any free-form text — handles common formats."""
    found: set[str] = set()

    for y, m, d in ISO_RE.findall(raw):
        try:
            found.add(date(int(y), int(m), int(d)).isoformat())
        except ValueError:
            pass

    for d, mname, y in DM_RE.findall(raw):
        m = MONTHS.get(mname.lower())
        if m:
            try:
                found.add(date(int(y), m, int(d)).isoformat())
            except ValueError:
                pass

    for mname, d, y in MD_RE.findall(raw):
        m = MONTHS.get(mname.lower())
        if m:
            try:
                found.add(date(int(y), m, int(d)).isoformat())
            except ValueError:
                pass

    # DD/MM/YYYY (UK) — assume UK order since this is the BoE/ECB use case
    for a, b, y in SLASH_RE.findall(raw):
        try:
            found.add(date(int(y), int(b), int(a)).isoformat())
        except ValueError:
            pass

    return sorted(found)


def prompt_dates(label: str, url: str) -> list[str]:
    print(f"\n──── {label} ────")
    print(f"Source: {url}")
    print("Opening in your browser…")
    try:
        webbrowser.open(url, new=2)
    except Exception:
        pass

    print(
        "\nCopy the next 12 months of meeting dates from that page and paste them below.\n"
        "Any format works — YYYY-MM-DD, '7 May 2027', 'Feb 5, 2027', DD/MM/YYYY — the\n"
        "script will pick out every date it recognises.\n"
        "Finish with an empty line. Leave blank to skip this source.\n"
    )

    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line)

    if not lines:
        print(f"(skipped {label})")
        return []

    dates = extract_dates("\n".join(lines))
    if not dates:
        print(
            f"⚠  Couldn't find any dates in what you pasted. Skipping {label}.\n"
            f"    Open {CONFIG} and edit the constant manually if needed."
        )
        return []

    print(f"\nParsed {len(dates)} dates for {label}:")
    for d in dates:
        print(f"   • {d}")
    confirm = input("\nLooks right? [Y/n] ").strip().lower()
    if confirm == "n":
        print(f"(skipped {label})")
        return []
    return dates


def rewrite_constant(content: str, name: str, dates: list[str]) -> tuple[str, bool]:
    """Replace the named list literal in fetch_calendar.py with new dates."""
    formatted = "\n    ".join(f'"{d}",' for d in dates)
    today = date.today().isoformat()
    replacement = (
        f"{name} = [\n"
        f"    # Refreshed by scripts/refresh_committee_dates.py on {today}\n"
        f"    {formatted}\n"
        f"]"
    )
    pattern = re.compile(rf"^{re.escape(name)}\s*=\s*\[[^\]]*\]", re.MULTILINE | re.DOTALL)
    new, count = pattern.subn(replacement, content, count=1)
    return new, count > 0


def main() -> int:
    print("\n══════════════════════════════════════════════════════════════")
    print("   Annual committee-dates refresh")
    print("   For BOE_MPC_HARDCODED and ECB_HARDCODED in fetch_calendar.py")
    print("══════════════════════════════════════════════════════════════")

    if not CONFIG.exists():
        print(f"ERROR: cannot find {CONFIG}")
        return 1

    boe_dates = prompt_dates("Bank of England MPC", BOE_URL)
    ecb_dates = prompt_dates("ECB Governing Council", ECB_URL)

    if not boe_dates and not ecb_dates:
        print("\nNothing to update — exiting.")
        return 0

    content = CONFIG.read_text(encoding="utf-8")
    changed: list[str] = []
    if boe_dates:
        content, ok = rewrite_constant(content, "BOE_MPC_HARDCODED", boe_dates)
        if ok:    changed.append("BOE_MPC_HARDCODED")
        else:     print("⚠  Could not locate BOE_MPC_HARDCODED in fetch_calendar.py")
    if ecb_dates:
        content, ok = rewrite_constant(content, "ECB_HARDCODED", ecb_dates)
        if ok:    changed.append("ECB_HARDCODED")
        else:     print("⚠  Could not locate ECB_HARDCODED in fetch_calendar.py")

    if not changed:
        print("\nNo changes written.")
        return 1

    CONFIG.write_text(content, encoding="utf-8")
    print(f"\n✓ Updated {', '.join(changed)} in {CONFIG.name}.")

    print(
        "\nNext steps:\n"
        "  1. Verify the diff:\n"
        "         git diff scripts/fetch_calendar.py\n"
        "  2. Regenerate the calendar and health files:\n"
        "         python scripts/fetch_calendar.py\n"
        "         python scripts/build_health.py\n"
        "  3. Commit and push:\n"
        f"         git add -A && git commit -m \"chore: refresh committee dates {date.today().year + 1}\" && git push"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
