import base64
from email import message_from_bytes
from email.header import decode_header

from src.generation.gemini_letter_generator import LetterDraft
from src.models import JobPosting
from src.notifications.gmail_draft import GmailDraftCreator, build_draft_message


def make_posting():
    return JobPosting(
        company="Amundi",
        title="Stage Analyste Gestion Actions",
        url="https://jobs.amundi.com/1",
        description="...",
        category="A",
    )


def decode_message(raw_message: dict):
    raw_bytes = base64.urlsafe_b64decode(raw_message["message"]["raw"])
    return message_from_bytes(raw_bytes)


def decoded_subject(parsed) -> str:
    parts = decode_header(parsed["Subject"])
    return "".join(part.decode(charset or "utf-8") if isinstance(part, bytes) else part for part, charset in parts)


def test_build_draft_message_subject_matches_expected_format():
    letter = LetterDraft(letter_text="Madame, Monsieur,...")
    message = build_draft_message(make_posting(), letter)

    parsed = decode_message(message)
    assert decoded_subject(parsed) == "Candidature Stage AM — Amundi — Stage Analyste Gestion Actions"


def test_build_draft_message_body_contains_letter_text():
    letter = LetterDraft(letter_text="Madame, Monsieur, corps de la lettre.")
    message = build_draft_message(make_posting(), letter)

    parsed = decode_message(message)
    body = parsed.get_payload(decode=True).decode("utf-8")
    assert "Madame, Monsieur, corps de la lettre." in body


def test_build_draft_message_body_flags_uncertain_elements_when_present():
    letter = LetterDraft(letter_text="Corps.", uncertain_elements=["Nom du recruteur", "Date de début"])
    message = build_draft_message(make_posting(), letter)

    parsed = decode_message(message)
    body = parsed.get_payload(decode=True).decode("utf-8")
    assert "Nom du recruteur" in body
    assert "Date de début" in body
    assert body.index("Nom du recruteur") < body.index("Corps.")


def test_build_draft_message_omits_verification_block_when_no_uncertain_elements():
    letter = LetterDraft(letter_text="Corps.", uncertain_elements=[])
    message = build_draft_message(make_posting(), letter)

    parsed = decode_message(message)
    body = parsed.get_payload(decode=True).decode("utf-8")
    assert "À vérifier" not in body


class FakeDraftsResource:
    def __init__(self):
        self.created_calls: list[dict] = []

    def create(self, userId, body):
        self.created_calls.append({"userId": userId, "body": body})
        return FakeExecutable({"id": "fake-draft-id"})


class FakeExecutable:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class FakeUsersResource:
    def __init__(self):
        self._drafts = FakeDraftsResource()

    def drafts(self):
        return self._drafts


class FakeGmailService:
    def __init__(self):
        self._users = FakeUsersResource()

    def users(self):
        return self._users


def test_create_draft_calls_gmail_drafts_create_and_returns_draft_id():
    service = FakeGmailService()
    creator = GmailDraftCreator(service)
    letter = LetterDraft(letter_text="Corps.")

    draft_id = creator.create_draft(make_posting(), letter)

    assert draft_id == "fake-draft-id"
    sent = service.users().drafts().created_calls[0]
    assert sent["userId"] == "me"
    assert "raw" in sent["body"]["message"]
