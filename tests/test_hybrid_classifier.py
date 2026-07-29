from src.classification.gemini_classifier import ClassificationResult
from src.classification.hybrid_classifier import HybridClassifier
from src.models import JobPosting


def posting(title):
    return JobPosting(company="Amundi", title=title, url="https://example.com/1", description="")


class FakeGeminiClassifier:
    def __init__(self, result):
        self._result = result
        self.calls = 0

    def classify(self, posting):
        self.calls += 1
        return self._result


def test_uses_rule_based_result_without_calling_gemini_when_confident():
    gemini = FakeGeminiClassifier(ClassificationResult(category="B", language="fr", to_verify=False))
    hybrid = HybridClassifier(gemini_classifier=gemini)

    result = hybrid.classify(posting("Stage - Chargé Marketing Financier H/F"))

    assert result.category == "N"
    assert gemini.calls == 0


def test_falls_back_to_gemini_when_rule_based_is_not_confident():
    gemini_result = ClassificationResult(category="A", language="fr", to_verify=True, reason="Cas limite ESG")
    gemini = FakeGeminiClassifier(gemini_result)
    hybrid = HybridClassifier(gemini_classifier=gemini)

    result = hybrid.classify(posting("Stage H/F - Analyste ESG/ISR (Gestion Obligataire) – Janvier 2027"))

    assert result is gemini_result
    assert gemini.calls == 1
