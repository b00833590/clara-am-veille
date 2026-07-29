import json
from types import SimpleNamespace

from src.gemini_retry import RateLimiter
from src.generation.gemini_letter_generator import GeminiLetterGenerator
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


def make_posting(**overrides):
    defaults = dict(
        company="Amundi",
        title="Stage Analyste Gestion Actions",
        url="https://jobs.amundi.com/1",
        description="Stage au sein de l'équipe de gestion actions.",
        category="A",
        language="fr",
    )
    defaults.update(overrides)
    return JobPosting(**defaults)


def make_generator(response_json: str):
    client = FakeGenAIClient(response_json)
    generator = GeminiLetterGenerator(
        client,
        cv_text="CV DE CLARA...",
        reference_letter_text="LETTRE DE REFERENCE...",
        rate_limiter=RateLimiter(min_interval=0),
        sleep_fn=lambda _: None,
    )
    return generator, client


def test_generate_returns_letter_text_and_uncertain_elements():
    response_json = json.dumps({"letter_text": "Madame, Monsieur,...", "uncertain_elements": ["Nom exact du recruteur"]})
    generator, _ = make_generator(response_json)

    draft = generator.generate(make_posting())

    assert draft.letter_text == "Madame, Monsieur,..."
    assert draft.uncertain_elements == ["Nom exact du recruteur"]


def test_generate_defaults_uncertain_elements_to_empty_list():
    response_json = json.dumps({"letter_text": "Madame, Monsieur,..."})
    generator, _ = make_generator(response_json)

    draft = generator.generate(make_posting())

    assert draft.uncertain_elements == []


def test_generate_includes_cv_and_reference_letter_in_prompt():
    response_json = json.dumps({"letter_text": "..."})
    generator, client = make_generator(response_json)

    generator.generate(make_posting())

    sent_input = client.interactions.calls[0]["input"]
    assert "CV DE CLARA..." in sent_input
    assert "LETTRE DE REFERENCE..." in sent_input


def test_generate_includes_posting_details_and_target_language_in_prompt():
    response_json = json.dumps({"letter_text": "..."})
    generator, client = make_generator(response_json)

    generator.generate(make_posting(company="Wellington Management", title="Internship - Investment Team", language="en"))

    sent_input = client.interactions.calls[0]["input"]
    assert "Wellington Management" in sent_input
    assert "Internship - Investment Team" in sent_input
    assert "en" in sent_input


def test_generate_uses_gemini_3_5_flash_model():
    response_json = json.dumps({"letter_text": "..."})
    generator, client = make_generator(response_json)

    generator.generate(make_posting())

    assert client.interactions.calls[0]["model"] == "gemini-3.5-flash"
