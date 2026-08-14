"""Completeness gate for the backend message catalog. Python has no `keyof` to enforce this at
the type level (unlike the frontend's de.ts, typed against TranslationKey) — this test is the
equivalent guarantee: every English key must have a German counterpart with the same
{placeholder} set, or the catalog has silently drifted."""
import re

from mobility_advisor.messages import de, en


def _placeholders(template: str) -> set[str]:
    # Matches {name} and {name:spec} (e.g. the {delta:+d} format-spec case in alt.co2Impact.value)
    # but not the standalone {{ }} literal-brace escapes, which .format() also supports.
    return {name.split(":")[0].split("!")[0] for name in re.findall(r"(?<!\{)\{([^{}]+)\}(?!\})", template)}


def test_every_english_key_has_a_german_translation():
    missing = set(en.MESSAGES) - set(de.MESSAGES)
    assert not missing, f"de.py is missing translations for: {sorted(missing)}"


def test_no_orphaned_german_keys():
    # A German key with no English counterpart is dead (t() always falls back to en.MESSAGES,
    # so nothing ever resolves it) or, worse, a typo'd duplicate of a real key.
    extra = set(de.MESSAGES) - set(en.MESSAGES)
    assert not extra, f"de.py has keys not present in en.py: {sorted(extra)}"


def test_placeholder_sets_match():
    mismatches = {}
    for key, en_template in en.MESSAGES.items():
        de_template = de.MESSAGES.get(key)
        if de_template is None:
            continue  # already reported by test_every_english_key_has_a_german_translation
        en_ph, de_ph = _placeholders(en_template), _placeholders(de_template)
        if en_ph != de_ph:
            mismatches[key] = {"en": sorted(en_ph), "de": sorted(de_ph)}
    assert not mismatches, f"placeholder mismatch: {mismatches}"


def test_catalog_values_are_all_strings():
    for catalog in (en.MESSAGES, de.MESSAGES):
        for key, value in catalog.items():
            assert isinstance(value, str), f"{key!r} is not a string: {value!r}"
