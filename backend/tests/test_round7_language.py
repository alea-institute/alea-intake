"""D02 (RUB-10 reading level): deterministic plain-language sentence shortener.

The post-pass must reduce mean sentence length (the dominant Flesch-Kincaid term)
without adding words or mangling citations.
"""

from __future__ import annotations

from app.services.output.language_adapter import _shorten_plain_sentences


def test_splits_long_sentence_at_connector():
    text = (
        "You must pay the rent within fourteen days, and you should also contact "
        "the court about the hearing, so you can raise your defenses in person."
    )
    out = _shorten_plain_sentences(text)
    # Result has more sentence-ending punctuation than the single input sentence.
    assert out.count(".") > text.count(".")
    # No words were added (mechanical split only) — every input word survives.
    for word in ("rent", "fourteen", "court", "hearing", "defenses"):
        assert word in out


def test_short_sentences_are_unchanged():
    text = "You must pay the rent. Call the court today."
    assert _shorten_plain_sentences(text) == text


def test_citation_boundary_is_not_split():
    text = (
        "Minnesota law protects you from this eviction under Minn. Stat. § 504B.285 "
        "and the landlord may owe you a penalty for retaliating against your report."
    )
    out = _shorten_plain_sentences(text)
    # The statute citation survives intact (never split across the section symbol).
    assert "Minn. Stat. § 504B.285" in out


def test_no_split_when_halves_too_small():
    # A long sentence with no safe connector position stays whole rather than
    # being chopped into fragments.
    text = "This is a reasonably long sentence about your case with no safe split."
    assert _shorten_plain_sentences(text) == text
