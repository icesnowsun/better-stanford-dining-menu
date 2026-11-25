#!/usr/bin/env python3
"""Fail if R&DE's hours page has moved since config/halls.json was checked against it.

The hours in config/halls.json are typed in by hand from the hours page (see
bsdm/hours.py for why they are not parsed), so a change on that page -- a
holiday closure, a new quarter -- is a job for a person. update.py has always
noticed, but only as a warning in a green log, which is a warning nobody reads.
This runs at the end of the nightly job, like check_source.py, and goes red with
what moved, so GitHub sends the mail.

It stays red every night until the page is recorded as checked: re-read the
page, edit config/halls.json to match if it needs it, then run the "Accept the
hours page" workflow from the Actions tab (`make hours-accept` on a laptop).
Taking upstream's hours (the "Upstream hours" pull request) brings upstream's
snapshot with them, which does the same.

A page that cannot be fetched is not a finding: that is the network, and the
next night looks again.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bsdm import hours as hourslib  # noqa: E402

SNAPSHOT = ROOT / "data" / "hours_snapshot.json"
NO_SNAPSHOT = "(no snapshot yet)"


def main() -> int:
    try:
        moved = hourslib.diff(SNAPSHOT)
    except Exception as exc:  # the network, not R&DE
        print(f"Could not read the hours page ({exc}); the next run looks again.")
        return 0
    if moved == NO_SNAPSHOT:
        print("No hours snapshot yet -- scripts/update.py records one on its first run.")
        return 0
    if not moved.strip():
        print("Hours page unchanged since config/halls.json was last checked against it.")
        return 0

    print("!! R&DE's hours page has changed since config/halls.json was last checked.")
    print(f"   {hourslib.HOURS_URL}\n")
    print(moved)
    print("\nRe-read the page and edit config/halls.json to match if it needs it, then run")
    print("the 'Accept the hours page' workflow (Actions tab) to record the page as checked.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
