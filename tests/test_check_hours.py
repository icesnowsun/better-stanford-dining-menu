"""scripts/check_hours.py: a moved hours page goes red, and nothing else does."""

from __future__ import annotations

import json

from bsdm import hours as hourslib
from conftest import load_script

check_hours = load_script("check_hours")


def test_an_unchanged_page_is_green(monkeypatch, capsys):
    monkeypatch.setattr(check_hours.hourslib, "diff", lambda path: "")
    assert check_hours.main() == 0
    assert "unchanged" in capsys.readouterr().out


def test_a_moved_page_goes_red_and_says_what_moved(monkeypatch, capsys):
    moved = "--- snapshot\n+++ live\n-Wilbur 7:30am - 8pm\n+Wilbur closed until Nov 28"
    monkeypatch.setattr(check_hours.hourslib, "diff", lambda path: moved)
    assert check_hours.main() == 1
    out = capsys.readouterr().out
    assert "+Wilbur closed until Nov 28" in out
    assert check_hours.hourslib.HOURS_URL in out
    assert "Accept the hours page" in out, "it says how to turn it green again"


def test_a_page_that_cannot_be_fetched_is_not_a_finding(monkeypatch):
    """That is the network, not R&DE; the next night looks again."""
    def offline(path):
        raise ConnectionError("no route to host")

    monkeypatch.setattr(check_hours.hourslib, "diff", offline)
    assert check_hours.main() == 0


def test_the_fortnightly_specials_link_is_not_an_hours_change(tmp_path, monkeypatch):
    """The hours section links the current fortnight's dinner specials, and that
    link's dates move every two weeks. The hours are what a person re-checks."""
    old = ("Arrillaga Family Dining Commons\nMonday - Friday 7:30am - 8:00pm\n"
           "View Monday - Friday Dinner Specials at our Dining Halls for Oct 26 - Nov 6")
    snapshot = tmp_path / "hours_snapshot.json"
    snapshot.write_text(json.dumps({"sha256": "x", "url": hourslib.HOURS_URL, "text": old}))

    new = old.replace("Oct 26 - Nov 6", "Nov 23 - Dec 4")
    monkeypatch.setattr(hourslib, "fetch_hours_text", lambda *a, **kw: new)
    assert hourslib.diff(snapshot) == ""

    closed = new.replace("7:30am - 8:00pm", "Closed until Nov 30")
    monkeypatch.setattr(hourslib, "fetch_hours_text", lambda *a, **kw: closed)
    assert "+Monday - Friday Closed until Nov 30" in hourslib.diff(snapshot)


def test_no_snapshot_yet_is_not_a_finding(monkeypatch):
    monkeypatch.setattr(check_hours.hourslib, "diff", lambda path: check_hours.NO_SNAPSHOT)
    assert check_hours.main() == 0
