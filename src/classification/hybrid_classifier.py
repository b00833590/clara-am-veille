from typing import Protocol

from src.classification.gemini_classifier import ClassificationResult
from src.classification.rule_based_classifier import RuleBasedClassifier
from src.models import JobPosting


class _GeminiLikeClassifier(Protocol):
    def classify(self, posting: JobPosting) -> ClassificationResult: ...


class HybridClassifier:
    """Tries the deterministic rule-based classifier first; only spends
    Gemini quota on postings the rules aren't confident about. Validated
    against the real 2026-07-22 live run: resolves the unambiguous majority
    (marketing/HR/legal/compliance/risk/ops exclusions, clear AM-core
    inclusions) without a single API call, while still escalating every
    genuinely ambiguous or nuance-dependent case (e.g. ESG/ISR) to Gemini.
    """

    def __init__(self, gemini_classifier: _GeminiLikeClassifier, rule_based_classifier: RuleBasedClassifier | None = None):
        self._gemini_classifier = gemini_classifier
        self._rule_based_classifier = rule_based_classifier or RuleBasedClassifier()

    def classify(self, posting: JobPosting) -> ClassificationResult:
        rule_result = self._rule_based_classifier.classify(posting)
        if rule_result is not None:
            return rule_result
        return self._gemini_classifier.classify(posting)
