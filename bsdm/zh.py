"""The translated layers: dish names translated whole, ingredients term by term.

Chinese came first, and is what every function here means when no language is
named. Spanish uses the same machinery with a table of its own, data/es.json, so
a Spanish catch-up never rewrites a line of the Chinese.

Ingredient text is deliberately not translated as prose. R&DE ingredient strings
are lists drawn from a small, heavily repeated vocabulary -- one full week is
~2,600 dish rows but only ~870 distinct terms, and "salt" alone accounts for 247
of them -- so the vocabulary is translated once and the list is reassembled per
dish in the browser. That keeps the wording identical between dishes, and makes
a new day's menu nearly free: a new dish costs one name plus whichever handful of
its terms have never been seen before.

`terms_in` and `norm` are mirrored in web/app.js, which reassembles the list on
the page. The two tokenizers must agree exactly: anything the page splits out but
this file never offered for translation falls back to English and shows up as a
stray English word mid-sentence.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from bsdm import menus as menuslib

# The separators an ingredient list is built from, kept in the split so the page
# can put the list back together with Chinese punctuation. Source text is not
# always balanced -- a few strings open a parenthesis and never close it, and one
# closes a bracket it never opened -- so the split is structure-free on purpose:
# every separator is translated where it stands rather than parsed into a tree.
_SPLIT = re.compile(r"([,()\[\]])")
_SEPARATORS = frozenset(",()[]")

# {section: whether entries keep their English alongside}. Terms and specials are
# keyed by the English itself, so storing it again would be noise; dishes and
# halls are keyed by id, and the English is what makes the file reviewable by
# hand.
SECTIONS = {"dishes": True, "terms": False, "halls": True, "specials": False}

# The languages the site is translated into, beyond the English it is scraped in:
# {code: the name summarize() prints}. The code is the file name and the key a
# dish entry keeps its translation under.
LANGS = {"zh": "Chinese", "es": "Spanish"}


def norm(term: str) -> str:
    """The lookup key for one ingredient term. Mirrored in web/app.js."""
    return " ".join(term.split()).lower()


def terms_in(ingredients: str) -> list[str]:
    """Every translatable term in an ingredient string, in order."""
    out = []
    for piece in _SPLIT.split(ingredients or ""):
        if piece in _SEPARATORS:
            continue
        if key := norm(piece):
            out.append(key)
    return out


def path_for(root: Path, lang: str = "zh") -> Path:
    return root / "data" / f"{lang}.json"


def load(root: Path, lang: str = "zh") -> dict:
    path = path_for(root, lang)
    table = json.loads(path.read_text()) if path.exists() else {}
    for section in SECTIONS:
        table.setdefault(section, {})
    return table


def save(root: Path, table: dict, lang: str = "zh") -> None:
    path_for(root, lang).write_text(
        json.dumps(table, indent=1, ensure_ascii=False, sort_keys=True) + "\n"
    )


def get(table: dict, section: str, key: str, lang: str = "zh") -> str | None:
    """The translation of one key, or None if it has not been translated."""
    entry = table.get(section, {}).get(key)
    if isinstance(entry, str):
        return entry or None
    return (entry or {}).get(lang) or None


def put(table: dict, section: str, key: str, english: str, translated: str,
        lang: str = "zh") -> None:
    table.setdefault(section, {})[key] = (
        {"en": english, lang: translated} if SECTIONS[section] else translated
    )


def merge(root: Path, section: str, pairs: dict[str, tuple[str, str]],
          lang: str = "zh") -> None:
    """Merge one batch of translations into the table on disk.

    The table is re-read before every write rather than held in memory: a first
    run makes a couple of dozen model calls over several minutes and has to
    survive a Ctrl-C, and a wholesale write would drop anything another run --
    or a hand edit -- had added in the meantime.
    """
    table = load(root, lang)
    for key, (english, translated) in pairs.items():
        put(table, section, key, english, translated, lang)
    save(root, table, lang)


def wanted(root: Path) -> dict[str, dict[str, str]]:
    """Everything a translated site needs, as {section: {key: English source}}.

    The same for every language: what needs translating is what the menus say.

    Terms are collected from the stored menus rather than from the catalog: the
    catalog keeps one ingredient string per dish, but the site publishes a
    variant per hall, and Branner's allergen-free recipes list different things.
    """
    catalog = json.loads((root / "data" / "dishes.json").read_text())
    names = {did: entry["name"] for did, entry in catalog.items()}

    # Every menu ever stored, not the live window: a term seen once and never
    # answered for -- a dropped batch, a run that never happened -- has to stay
    # on the list, or it silently never gets asked about again.
    terms: dict[str, str] = {}
    for path in menuslib.history(root):
        day = json.loads(path.read_text())
        for meals in day["halls"].values():
            for served in meals.values():
                for dish in served:
                    for term in terms_in(dish.get("ingredients") or ""):
                        terms[term] = term

    config = json.loads((root / "config" / "halls.json").read_text())
    halls = {h["id"]: h["concept"] for h in config["halls"] if h.get("concept")}

    # Specials are prose, not a list, so they are translated whole like a dish
    # name. Every calendar ever archived is offered, not just the current one:
    # they cost a line each, and the same dish comes round again.
    from bsdm import specials as specialslib
    specials = {text: text for text in specialslib.texts(root)}

    return {"dishes": names, "terms": terms, "halls": halls, "specials": specials}


def missing(root: Path, table: dict | None = None,
            lang: str = "zh") -> dict[str, dict[str, str]]:
    """The subset of `wanted` that has no translation yet."""
    table = load(root, lang) if table is None else table
    return {
        section: {k: en for k, en in entries.items() if not get(table, section, k, lang)}
        for section, entries in wanted(root).items()
    }


def summarize(root: Path, lang: str = "zh") -> str:
    table = load(root, lang)
    want = wanted(root)
    parts = []
    for section, label in (("dishes", "dish names"), ("terms", "ingredient terms"),
                           ("halls", "hall concepts"), ("specials", "specials")):
        total = len(want[section])
        have = sum(1 for k in want[section] if get(table, section, k, lang))
        parts.append(f"{have}/{total} {label}")
    return f"{LANGS[lang]}: " + " | ".join(parts)
