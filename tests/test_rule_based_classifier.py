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
# Now the sole classifier (2026-07-29, AM-strict): every case must resolve to
# a decision, never escalate.

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
        ("Stage - Inside Sales - Data-as-a-Service H/F", "N", "fr"),
        # Found live on 2026-07-29 running preview_run.py against Amundi's
        # real postings: fell through to the "no signal" bucket and was
        # wrongly defaulted to A — a generalist tech role, not AM.
        ("Stage - Data ingénieur H/F", "N", "fr"),
        # Found live on 2026-07-30 running the real GitHub Actions pipeline:
        # all four fell through to the old "no signal" default and were
        # emailed to Clara by mistake — none of these are Asset Management.
        ("2027 Q2 - M&A Internship - Frankfurt and Munich", "N", "en"),
        ("January 2027 - M&A internship - Paris", "N", "en"),
        ("March 2027 - Investment Banking intern - Real Estate team - Paris", "N", "en"),
        ("Stage - Contrôleur financier (6/12 mois) H/F", "N", "fr"),
        ("Intern - EA/Team Assistant", "N", "en"),
        ("Stage - Communication visuelle – Formation en Epargne Salariale et Retraite  H/F", "N", "fr"),
        # "Gestion privée" is a deliberate inclusion (Clara's choice, 2026-07-30)
        # despite its sales-adjacent tone — now a confident match, not a
        # "no signal" default.
        ("Stage H/F - Développement Gestion Privée – Paris – Janvier 2027", "A", "fr"),
    ],
)
def test_matches_real_ground_truth_from_live_run(title, expected_category, expected_language):
    result = classify(title)

    assert result.category == expected_category
    assert result.language == expected_language
    assert result.to_verify is False


def test_esg_integrated_into_portfolio_management_is_classified_a_and_flagged():
    # The explicit nuance the original prompt carved out: ESG-integrated-in-
    # portfolio-management is A, never resolved by keyword alone — flagged
    # to_verify=True since it's a judgment call, not a confident rule match.
    result = classify("Stage Analyste ESG au sein de la Gestion Obligataire H/F")
    assert result.category == "A"
    assert result.to_verify is True


def test_esg_standalone_function_is_classified_n_and_flagged():
    result = classify("Stage H/F - Chargé de Mission RSE – Janvier 2027")
    assert result.category == "N"
    assert result.to_verify is True


def test_conflicting_signals_resolve_to_n_and_are_flagged():
    # Contains both a strong exclude signal (marketing) and a strong include
    # signal (portfolio management) — the stated function usually describes
    # the job better than the team it supports, but this is a judgment call.
    result = classify("Stage Marketing pour l'équipe Portfolio Management H/F")
    assert result.category == "N"
    assert result.to_verify is True


@pytest.mark.parametrize(
    "title",
    [
        "Stage - Projets Amundi Immobilier H/F",
    ],
)
def test_no_strong_signal_either_way_defaults_to_a_and_is_flagged(title):
    # No auto-exclude, no auto-include match: favors showing Clara a possible
    # opportunity over silently dropping it, consistent with the original
    # "en cas de doute, on montre" philosophy — she can always dismiss it.
    result = classify(title)
    assert result.category == "A"
    assert result.to_verify is True


def test_wealth_management_is_a_confident_inclusion():
    result = classify("Private Banking Internship - Wealth Management Team")
    assert result.category == "A"
    assert result.to_verify is False


def test_language_uncertain_defaults_to_french_and_is_flagged():
    # Category is clear (DPM Clients matches), but nothing in the title
    # signals a language — defaults to "fr" (majority of target postings)
    # rather than guessing wrong, and is flagged for Clara to confirm.
    result = classify("DPM Clients M/F")
    assert result.category == "A"
    assert result.language == "fr"
    assert result.to_verify is True
