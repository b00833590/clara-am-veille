import base64
from email.mime.text import MIMEText

from src.generation.gemini_letter_generator import LetterDraft
from src.models import JobPosting


def build_draft_message(posting: JobPosting, letter: LetterDraft) -> dict:
    subject = f"Candidature Stage AM — {posting.company} — {posting.title}"

    body_lines = []
    if letter.uncertain_elements:
        body_lines.append("⚠️ À vérifier avant l'envoi :")
        body_lines.extend(f"- {element}" for element in letter.uncertain_elements)
        body_lines.append("")
    body_lines.append(letter.letter_text)

    mime_message = MIMEText("\n".join(body_lines), _charset="utf-8")
    mime_message["Subject"] = subject

    raw = base64.urlsafe_b64encode(mime_message.as_bytes()).decode("ascii")
    return {"message": {"raw": raw}}


class GmailDraftCreator:
    def __init__(self, gmail_service):
        self._service = gmail_service

    def create_draft(self, posting: JobPosting, letter: LetterDraft) -> str:
        body = build_draft_message(posting, letter)
        result = self._service.users().drafts().create(userId="me", body=body).execute()
        return result.get("id", "")
