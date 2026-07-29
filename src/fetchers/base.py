import re
from typing import Protocol

from src.models import JobPosting


class Fetcher(Protocol):
    def fetch(self) -> list[JobPosting]: ...


def label_of(value) -> str:
    if isinstance(value, dict):
        return value.get("label", "") or ""
    return value or ""


INTERNSHIP_KEYWORDS = ("stage", "stagiaire", "intern", "internship", "alternance", "alternant")

# Word-boundary matching: a plain substring check would flag "contrôle
# interne" or "international" as internships, since "intern" is a substring
# of "interne"/"international" — a real false positive hit live against
# Edmond de Rothschild (compliance/audit roles).
_INTERNSHIP_PATTERN = re.compile(r"\b(" + "|".join(INTERNSHIP_KEYWORDS) + r")\b")


def looks_like_internship(*texts: str) -> bool:
    haystack = " ".join(texts).lower()
    return bool(_INTERNSHIP_PATTERN.search(haystack))
