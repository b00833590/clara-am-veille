import json
from types import SimpleNamespace

from src.classification.gemini_classifier import GeminiClassifier
from src.gemini_retry import RateLimiter
from src.models import JobPosting


class FakeInteractions:
    def __init__(self, response_json: str):
        self._response_json = response_json
        self.calls: list[dict] = []

    def create(self, model, input, response_format):
        self.calls.append({"model": model, "input": input, "response_format": response_format})
        return SimpleNamespace(output_text=self._response_json)


class FakeGenAIClient:
    def __init__(self, response_json: str):
        self.interactions = FakeInteractions(response_json)


def make_posting():
    return JobPosting(
        company="Amundi",
        title="Stage Analyste Gestion Actions",
        url="https://jobs.amundi.com/1",
        description="Stage au sein de l'équipe de gestion actions, analyse de portefeuille.",
    )


def test_classify_parses_category_language_and_to_verify():
    response_json = json.dumps({"category": "A", "language": "fr", "to_verify": False, "reason": "Stage analyste AM"})
    client = FakeGenAIClient(response_json)
    classifier = GeminiClassifier(client, rate_limiter=RateLimiter(min_interval=0), sleep_fn=lambda _: None)

    result = classifier.classify(make_posting())

    assert result.category == "A"
    assert result.language == "fr"
    assert result.to_verify is False


def test_classify_uses_gemini_3_5_flash_model():
    response_json = json.dumps({"category": "B", "language": "en", "to_verify": True, "reason": ""})
    client = FakeGenAIClient(response_json)
    classifier = GeminiClassifier(client, rate_limiter=RateLimiter(min_interval=0), sleep_fn=lambda _: None)

    classifier.classify(make_posting())

    assert client.interactions.calls[0]["model"] == "gemini-3.5-flash"


def test_classify_includes_posting_title_and_company_in_prompt():
    response_json = json.dumps({"category": "A", "language": "fr", "to_verify": False, "reason": ""})
    client = FakeGenAIClient(response_json)
    classifier = GeminiClassifier(client, rate_limiter=RateLimiter(min_interval=0), sleep_fn=lambda _: None)

    classifier.classify(make_posting())

    sent_input = client.interactions.calls[0]["input"]
    assert "Stage Analyste Gestion Actions" in sent_input
    assert "Amundi" in sent_input


def test_classify_requests_json_response_format():
    response_json = json.dumps({"category": "A", "language": "fr", "to_verify": False, "reason": ""})
    client = FakeGenAIClient(response_json)
    classifier = GeminiClassifier(client, rate_limiter=RateLimiter(min_interval=0), sleep_fn=lambda _: None)

    classifier.classify(make_posting())

    response_format = client.interactions.calls[0]["response_format"]
    assert response_format["mime_type"] == "application/json"
