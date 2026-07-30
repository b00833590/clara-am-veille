import re

from src.classification.models import ClassificationResult
from src.models import JobPosting

# ESG/ISR/RSE/durable is the one deliberate nuance carve-out: integrated
# directly into portfolio management (e.g. "Analyste ESG au sein de la
# Gestion Obligataire") is a core AM role, while a standalone sustainability
# function is not — resolved below by checking for an AM-core signal
# alongside it, not by keyword alone.
_ESG_PATTERN = re.compile(r"\b(esg|isr|rse|sustainab|durabl)", re.IGNORECASE)

# Strong, unambiguous exclusion signals — validated against the real
# 2026-07-22 live Gemini run: caught every real N posting on title alone that
# day, zero false negatives against that day's real A postings. "Vente"/
# "sales" and "développement commercial" added when classification went
# AM-strict (2026-07-29) — Clara wants AM investment roles only, no more
# finance-adjacent "Catégorie B" safety net. Corporate finance/M&A/IB,
# contrôle financier, assistanat, and a broadened "communication" added
# 2026-07-30 after real false positives got emailed (Lazard M&A/IB
# internships, "Contrôleur financier", "Team Assistant", "Communication
# visuelle" — none matched the old exclude list, so they fell through to
# the "no signal" default and were sent to Clara by mistake).
_AUTO_EXCLUDE_PATTERN = re.compile(
    r"\b("
    r"marketing|charg[ée] de com|communication|"
    r"ressources humaines|\brh\b|talent acquisition|sourcing (de )?talents?|recruiting|recrutement|"
    r"juridique|\blegal\b|compliance|conformit[ée]|\baml\b|\bkyc\b|"
    r"audit interne|contr[oô]le de gestion|contr[oô]leur financier|financial controller|contr[oô]le financier|"
    r"d[ée]veloppement logiciel|data science|data engineer|data ing[ée]nieur|"
    r"ing[ée]nieur (data|informatique|logiciel|syst[èe]mes?)|intelligence artificielle|"
    r"coordination (op[ée]rationnelle|administrative)|fund dealing|middle[- ]office|"
    r"business development|d[ée]veloppement (commercial|client[èe]le|d'affaires)|"
    r"product management|transformation|strat[ée]gie interne|"
    r"risk management|gestion des risques|contr[oô]le des risques|"
    r"\bvente\b|\bsales\b|inside sales|"
    r"m&a|mergers? (and|&) acquisitions?|investment banking|corporate finance|"
    r"leveraged finance|capital markets|debt advisory|restructuring|\bcoverage\b|"
    r"team assistant|executive assistant|assistant de direction|office assistant"
    r")\b",
    re.IGNORECASE,
)

# Strong, unambiguous AM-core signals. "Gestion privée"/"private banking"/
# "wealth management" added 2026-07-30 — deliberate choice by Clara despite
# the sales-adjacent tone, unlike M&A/IB which she wants excluded.
_AUTO_INCLUDE_PATTERN = re.compile(
    r"\b("
    r"discretionary portfolio management|dpm clients?|gestion de portefeuille|portfolio manage\w*|"
    r"investment analyst|investment specialist|equity research|fixed income analyst|"
    r"fixed income management|gestion obligataire|"
    r"multi[- ]asset|multi[- ]gestion|fund analyst|private equity|asset allocation|allocation d'actifs|"
    r"buy[- ]side research|recherche (investissement|actions|cr[ée]dit)|"
    r"analyste (fonds|financier|investissement|actions|cr[ée]dit)|"
    r"gestion d'actifs immobiliers|real estate asset management|g[ée]rant immobilier|"
    r"gestion priv[ée]e|private banking|wealth management"
    r")\b",
    re.IGNORECASE,
)

_GERMAN_MARKER_PATTERN = re.compile(r"\bm/w/d\b|\bpraktikum\b", re.IGNORECASE)
_FRENCH_MARKER_PATTERN = re.compile(r"\bh/f\b|\bstage\b", re.IGNORECASE)
_FRENCH_ACCENT_PATTERN = re.compile(r"[àâäéèêëîïôöùûüç]", re.IGNORECASE)
_ENGLISH_MARKER_PATTERN = re.compile(r"\binternship\b|\bintern\b", re.IGNORECASE)

_REASON_EXCLUDED = "Classé automatiquement par règle : fonction support/hors-AM identifiée dans le titre, aucun signal d'investissement présent."
_REASON_INCLUDED = "Classé automatiquement par règle : intitulé correspond directement à une fonction cœur de métier Asset Management."
_REASON_ESG_WITH_AM = "Mention ESG/ISR détectée aux côtés d'un signal de gestion d'actifs — classé A en tant qu'ESG intégré à la gestion de portefeuille, à confirmer."
_REASON_ESG_STANDALONE = "Mention ESG/ISR détectée sans signal de gestion d'actifs — classé N en tant que fonction ESG autonome, à confirmer."
_REASON_CONFLICTING = "Signaux contradictoires (fonction support ET terme AM tous deux présents) — la fonction énoncée l'emporte généralement sur l'équipe qu'elle sert, classé N, à confirmer."
_REASON_NO_SIGNAL = "Aucun signal fort ni d'exclusion ni d'inclusion dans le titre — classé A par défaut (mieux vaut vérifier une offre incertaine que rater une opportunité), à confirmer."
_REASON_LANGUAGE_UNCERTAIN_SUFFIX = " Langue non déterminée avec confiance à partir du titre — français supposé par défaut, à vérifier."


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
    """Sole classifier (2026-07-29) — no LLM in the loop for classification at
    all, since Clara wants AM-strict filtering (no more "Catégorie B" finance-
    adjacent safety net) and the classification volume across ~20 sources
    repeatedly overwhelmed the free Gemini tier's throughput. Always resolves
    to a decision (never escalates) — genuinely ambiguous cases are flagged
    with to_verify=True instead, for Clara to confirm manually. AI is now used
    only for cover letter generation, whose volume (a handful a week) is low
    enough that quota is a non-issue.
    """

    def classify(self, posting: JobPosting) -> ClassificationResult:
        haystack = f"{posting.title} {posting.description}"

        language = _detect_language(haystack)
        language_uncertain = language is None
        if language_uncertain:
            language = "fr"

        excluded = bool(_AUTO_EXCLUDE_PATTERN.search(haystack))
        included = bool(_AUTO_INCLUDE_PATTERN.search(haystack))
        esg_mentioned = bool(_ESG_PATTERN.search(haystack))

        if esg_mentioned:
            category = "A" if included else "N"
            reason = _REASON_ESG_WITH_AM if included else _REASON_ESG_STANDALONE
            return self._result(category, language, True, reason, language_uncertain)

        if excluded and included:
            return self._result("N", language, True, _REASON_CONFLICTING, language_uncertain)

        if excluded:
            return self._result("N", language, False, _REASON_EXCLUDED, language_uncertain)

        if included:
            return self._result("A", language, False, _REASON_INCLUDED, language_uncertain)

        return self._result("A", language, True, _REASON_NO_SIGNAL, language_uncertain)

    @staticmethod
    def _result(category: str, language: str, to_verify: bool, reason: str, language_uncertain: bool) -> ClassificationResult:
        if language_uncertain:
            to_verify = True
            reason = reason + _REASON_LANGUAGE_UNCERTAIN_SUFFIX
        return ClassificationResult(category=category, language=language, to_verify=to_verify, reason=reason)
