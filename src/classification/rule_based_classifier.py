import re

from src.classification.gemini_classifier import ClassificationResult
from src.models import JobPosting

# Keywords that must ALWAYS escalate to the LLM regardless of anything else —
# the classification prompt has an explicit nuance carve-out here (ESG/ISR
# integrated directly into portfolio management is A, ESG as a standalone
# function is N) that a keyword match alone cannot safely resolve.
_ALWAYS_ESCALATE_PATTERN = re.compile(r"\b(esg|isr|rse|sustainab|durabl)", re.IGNORECASE)

# Strong, unambiguous exclusion signals — validated against the real 2026-07-22
# live Gemini run: caught every real N posting on title alone that day, zero
# false negatives against that day's real A postings.
_AUTO_EXCLUDE_PATTERN = re.compile(
    r"\b("
    r"marketing|charg[ée] de com|communication (interne|externe)|"
    r"ressources humaines|\brh\b|talent acquisition|sourcing (de )?talents?|recruiting|recrutement|"
    r"juridique|\blegal\b|compliance|conformit[ée]|\baml\b|\bkyc\b|"
    r"audit interne|contr[oô]le de gestion|"
    r"d[ée]veloppement logiciel|data science|intelligence artificielle|"
    r"coordination (op[ée]rationnelle|administrative)|fund dealing|middle[- ]office|"
    r"business development|product management|transformation|strat[ée]gie interne|"
    r"risk management|gestion des risques|contr[oô]le des risques"
    r")\b",
    re.IGNORECASE,
)

# Strong, unambiguous AM-core signals.
_AUTO_INCLUDE_PATTERN = re.compile(
    r"\b("
    r"discretionary portfolio management|dpm clients?|gestion de portefeuille|portfolio manage\w*|"
    r"investment analyst|investment specialist|equity research|fixed income analyst|"
    r"multi[- ]asset|fund analyst|private equity|asset allocation|buy[- ]side research"
    r")\b",
    re.IGNORECASE,
)

_GERMAN_MARKER_PATTERN = re.compile(r"\bm/w/d\b|\bpraktikum\b", re.IGNORECASE)
_FRENCH_MARKER_PATTERN = re.compile(r"\bh/f\b|\bstage\b", re.IGNORECASE)
_FRENCH_ACCENT_PATTERN = re.compile(r"[àâäéèêëîïôöùûüç]", re.IGNORECASE)
_ENGLISH_MARKER_PATTERN = re.compile(r"\binternship\b|\bintern\b", re.IGNORECASE)


def _detect_language(haystack: str) -> str | None:
    if _GERMAN_MARKER_PATTERN.search(haystack):
        return "de"
    if _FRENCH_MARKER_PATTERN.search(haystack) or _FRENCH_ACCENT_PATTERN.search(haystack):
        return "fr"
    if _ENGLISH_MARKER_PATTERN.search(haystack):
        # "M/F" is used by both French and English postings in practice
        # (confirmed live on Amundi listings) — not a safe language signal.
        return "en"
    return None


class RuleBasedClassifier:
    """Deterministic first pass over a posting's title. Resolves the
    unambiguous majority without spending Gemini quota, escalating (returning
    None) anything genuinely ambiguous — including cases the prompt itself
    says need nuance (ESG/ISR), conflicting signals, and any posting whose
    language can't be confidently inferred (a wrong-language cover letter is
    worse than one extra Gemini call).
    """

    def classify(self, posting: JobPosting) -> ClassificationResult | None:
        haystack = f"{posting.title} {posting.description}"

        if _ALWAYS_ESCALATE_PATTERN.search(haystack):
            return None

        language = _detect_language(haystack)
        if language is None:
            return None

        excluded = bool(_AUTO_EXCLUDE_PATTERN.search(haystack))
        included = bool(_AUTO_INCLUDE_PATTERN.search(haystack))

        if excluded and not included:
            return ClassificationResult(
                category="N",
                language=language,
                to_verify=False,
                reason="Classé automatiquement par règle : fonction support/hors-AM identifiée dans le titre, aucun signal d'investissement présent.",
            )
        if included and not excluded:
            return ClassificationResult(
                category="A",
                language=language,
                to_verify=False,
                reason="Classé automatiquement par règle : intitulé correspond directement à une fonction cœur de métier Asset Management.",
            )

        return None
