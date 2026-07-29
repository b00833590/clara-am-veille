import re
from pathlib import Path

from src.fetchers.base import looks_like_internship

FETCHERS_DIR = Path(__file__).parent.parent / "src" / "fetchers"
# `response.text` on an HTTP response is encoding-guess-prone: requests falls
# back to guessing when a server's Content-Type omits a charset, and can
# guess wrong — confirmed live, produces "é" -> "Ã©" mojibake. Always read
# `.content` (raw bytes) and let BeautifulSoup's own HTML-aware encoding
# detection handle it instead. This deliberately only matches a variable
# literally named `response` (the convention every fetcher in this codebase
# uses for the requests Response object) so it doesn't false-positive on
# ordinary BeautifulSoup Tag.text usage like `title_el.text`.
_RESPONSE_DOT_TEXT_PATTERN = re.compile(r"\bresponse\.text\b")


def test_matches_stage_in_french_title():
    assert looks_like_internship("Stage Analyste Financier") is True


def test_matches_internship_in_english_title():
    assert looks_like_internship("Summer Internship - Investment Team") is True


def test_matches_alternance():
    assert looks_like_internship("Alternant Contrôle de Gestion") is True


def test_does_not_match_controle_interne():
    # "intern" is a substring of "interne" (French for "internal") — this
    # produced real false positives live against Edmond de Rothschild
    # (compliance/audit roles wrongly flagged as internships).
    assert looks_like_internship("CHARGÉ DE CONFORMITÉ ET DE CONTRÔLE INTERNE") is False


def test_does_not_match_audit_interne():
    assert looks_like_internship("RESPONSABLE DE MISSIONS D'AUDIT INTERNE") is False


def test_does_not_match_international():
    # "intern" is also a substring of "international".
    assert looks_like_internship("International Sales Analyst") is False


def test_matches_multiple_texts_combined():
    assert looks_like_internship("Portfolio Analyst", "Internship program for students") is True


def test_no_fetcher_uses_response_dot_text_directly():
    offenders = []
    for path in FETCHERS_DIR.glob("*.py"):
        content = path.read_text(encoding="utf-8")
        if _RESPONSE_DOT_TEXT_PATTERN.search(content):
            offenders.append(path.name)

    assert offenders == []
