import pytest

from src.classification.division import infer_division


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Stage H/F - Analyste Actions – Janvier 2027", "Equity"),
        ("Equity Research Intern", "Equity"),
        ("Stage H/F - Analyste Fixed Income Pôle High Yield – Janvier 2027", "Fixed Income"),
        ("Stage H/F - Gestion Obligataire", "Fixed Income"),
        ("Multi-Asset Portfolio Analyst", "Multi-Asset"),
        ("Stage - Allocation d'actifs", "Multi-Asset"),
        ("Stage Analyste ESG au sein de la Gestion Obligataire H/F", "ESG"),
        ("Private Equity Analyst Intern", "Private Markets"),
        ("Stage - Gestion d'actifs immobiliers", "Private Markets"),
        ("Private Banking Internship - Wealth Management Team", "Gestion Privée"),
        ("Stage H/F - Développement Gestion Privée – Paris", "Gestion Privée"),
        ("Investment Analyst Intern", ""),
        ("Stage - Contrôleur financier (6/12 mois) H/F", ""),
    ],
)
def test_infer_division(title, expected):
    assert infer_division(title) == expected


def test_esg_takes_priority_over_fixed_income_when_both_present():
    # Matches the classifier's own nuance: ESG-integrated-into-a-fixed-income
    # team is tagged ESG, not Fixed Income — it's the more specific signal
    # for what makes this posting notable.
    assert infer_division("Analyste ESG - Gestion Obligataire") == "ESG"
