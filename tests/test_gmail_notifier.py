import base64
from email import message_from_bytes
from email.header import decode_header

from src.classification.gemini_classifier import ClassificationResult
from src.models import JobPosting
from src.notifications.gmail_notifier import GmailNotifier, build_notification_message


def make_posting():
    return JobPosting(
        company="Amundi",
        title="Stage Analyste Gestion Actions",
        url="https://jobs.amundi.com/1",
        description="...",
        category="A",
    )


def decode_message(raw_message: dict):
    raw_bytes = base64.urlsafe_b64decode(raw_message["raw"])
    return message_from_bytes(raw_bytes)


def decoded_subject(parsed) -> str:
    parts = decode_header(parsed["Subject"])
    return "".join(part.decode(charset or "utf-8") if isinstance(part, bytes) else part for part, charset in parts)


def test_build_notification_message_contains_company_and_title_in_subject():
    message = build_notification_message(make_posting(), recipient_email="clara@example.com")

    parsed = decode_message(message)
    subject = decoded_subject(parsed)
    assert "Amundi" in subject
    assert "Stage Analyste Gestion Actions" in subject


def test_build_notification_message_sends_to_recipient():
    message = build_notification_message(make_posting(), recipient_email="clara@example.com")

    parsed = decode_message(message)
    assert parsed["To"] == "clara@example.com"


def test_build_notification_message_body_includes_classification_reason_when_to_verify():
    posting = JobPosting(
        company="Amundi",
        title="Stage Analyste",
        url="https://jobs.amundi.com/1",
        description="...",
        category="A",
        to_verify=True,
        classification_reason="Ambigu entre gestion privée et corporate banking",
    )
    message = build_notification_message(posting, recipient_email="clara@example.com")

    parsed = decode_message(message)
    body = parsed.get_payload(decode=True).decode("utf-8")
    assert "Ambigu entre gestion privée et corporate banking" in body


def test_build_notification_message_body_contains_link():
    message = build_notification_message(make_posting(), recipient_email="clara@example.com")

    parsed = decode_message(message)
    body = parsed.get_payload(decode=True).decode("utf-8")
    assert "https://jobs.amundi.com/1" in body


class FakeMessagesResource:
    def __init__(self):
        self.sent_calls: list[dict] = []

    def send(self, userId, body):
        self.sent_calls.append({"userId": userId, "body": body})
        return FakeExecutable(result={"id": "fake-message-id"})


class FakeExecutable:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class FakeUsersResource:
    def __init__(self):
        self._messages = FakeMessagesResource()

    def messages(self):
        return self._messages


class FakeGmailService:
    def __init__(self):
        self._users = FakeUsersResource()

    def users(self):
        return self._users


def test_notify_new_posting_calls_gmail_send_with_authenticated_user():
    service = FakeGmailService()
    notifier = GmailNotifier(service, recipient_email="clara@example.com")

    notifier.notify_new_posting(make_posting())

    sent = service.users().messages().sent_calls[0]
    assert sent["userId"] == "me"
    assert "raw" in sent["body"]
