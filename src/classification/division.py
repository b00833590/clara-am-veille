import re

# Best-effort tag for the tracking sheet's "Division/Équipe" column — purely
# informational (never affects A/N classification). First match wins, most
# specific signals checked first (e.g. "private equity" before a generic
# "equity" match would misfire on it).
_DIVISION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Private Markets", re.compile(r"\b(private equity|private markets|gestion d'actifs immobiliers|real estate|immobilier)\b", re.IGNORECASE)),
    ("Gestion Privée", re.compile(r"\b(gestion priv[ée]e|private banking|wealth management)\b", re.IGNORECASE)),
    ("ESG", re.compile(r"\b(esg|isr|rse|sustainab|durabl)\b", re.IGNORECASE)),
    ("Multi-Asset", re.compile(r"\b(multi[- ]asset|multi[- ]gestion|asset allocation|allocation d'actifs)\b", re.IGNORECASE)),
    ("Fixed Income", re.compile(r"\b(fixed income|gestion obligataire|obligataire|cr[ée]dit)\b", re.IGNORECASE)),
    ("Equity", re.compile(r"\b(equity|actions)\b", re.IGNORECASE)),
]


def infer_division(title: str, description: str = "") -> str:
    haystack = f"{title} {description}"
    for label, pattern in _DIVISION_PATTERNS:
        if pattern.search(haystack):
            return label
    return ""
