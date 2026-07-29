import pytest

from src.classification.rule_based_classifier import RuleBasedClassifier
from src.models import JobPosting


def posting(title, description=""):
    return JobPosting(company="Amundi", title=title, url="https://example.com/1", description=description)


def classify(title, description=""):
    return RuleBasedClassifier().classify(posting(title, description))


# --- Ground truth from the real 2026-07-22 live Gemini run (see conversation
# history) — these are not synthetic examples, they're the actual titles and
# actual correct category/language pairs Gemini itself produced that day.
# Cases the rule engine can't safely resolve (ambiguous or by design, e.g.
# ESG/ISR) are expected to return None (escalate), not guess.

@pytest.mark.parametrize(
    "title,expected_category,expected_language",
    [
        ("Stage -  Chargé Marketing Financier H/F", "N", "fr"),
        ("FC - Stage - AML/KYC Oversight H/F", "N", "fr"),
        ("STAGE ASSISTANT COORDINATION OPERATIONNELLE ET ADMINISTRATIVE H/F", "N", "fr"),
        ("STAGE - CHARGE DE COM INTERNE ET EXTERNE H/F", "N", "fr"),
        ("Internship – Product & Marketing Team Support M/F", "N", "en"),
        ("Stage - Assistant Marketing Stratégique H/F", "N", "fr"),
        ("Praktikum im Bereich Risk Management / Performance m/w/d", "N", "de"),
        ("FC - Stage Fund Dealing Support (6/12 months) H/F", "N", "fr"),
        ("Studentischer Mitarbeiter im Bereich Legal (20h/Woche) m/w/d", "N", "de"),
        ("Stage H/F - Risk Management – Janvier 2027", "N", "fr"),
        ("Stage H/F - Chargé de Projets - Intelligence Artificielle – Mars 2027", "N", "fr"),
        ("Investment specialist intern M/F", "A", "en"),
        ("Stage H/F - Private Equity – Janvier 2027", "A", "fr"),
    ],
)
def test_matches_real_ground_truth_from_live_run(title, expected_category, expected_language):
    result = classify(title)

    assert result is not None, f"expected a confident rule-based decision for {title!r}, got escalation"
    assert result.category == expected_category
    assert result.language == expected_language
    assert result.to_verify is False


@pytest.mark.parametrize(
    "title",
    [
        "Stage - Inside Sales - Data-as-a-Service H/F",  # no strong signal either way
        "Stage - Projets Amundi Immobilier H/F",  # no strong signal either way
        "DPM Clients M/F",  # category clear, but language can't be safely inferred from title alone
        "Stage H/F - Développement Gestion Privée – Paris – Janvier 2027",  # ambiguous: "développement" alone isn't a safe AM signal
        "Stage H/F - Analyste ESG/ISR (Gestion Obligataire) – Janvier 2027",  # deliberate: ESG/ISR always escalates
    ],
)
def test_escalates_ambiguous_or_edge_case_titles_rather_than_guessing(title):
    assert classify(title) is None


def test_esg_always_escalates_even_with_a_clear_am_team_name_alongside_it():
    # The explicit nuance the prompt carves out: ESG-integrated-in-portfolio-
    # management is a cas limite that needs the LLM's judgment, never a
    # keyword-only guess, regardless of what else is in the title.
    assert classify("Stage Analyste ESG au sein de la Gestion Obligataire H/F") is None


def test_conflicting_signals_escalate_rather_than_guess():
    # Contains both a strong exclude signal (marketing) and a strong include
    # signal (portfolio management) — must not silently pick one.
    result = classify("Stage Marketing pour l'équipe Portfolio Management H/F")
    assert result is None
