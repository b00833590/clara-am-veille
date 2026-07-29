import base64
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.generation.gemini_letter_generator import LetterDraft
from src.generation.pdf import text_to_pdf_bytes
from src.models import JobPosting


def _safe_filename_part(value: str) -> str:
    return "".join(c if c.isalnum() or c in " -_" else "_" for c in value).strip()


def build_draft_message(posting: JobPosting, letter: LetterDraft, cv_pdf_bytes: bytes | None = None) -> dict:
    """Assembles the "dossier de candidature" — decision (2026-07-29): the
    letter is Clara's real work product so it's generated fresh, but her CV
    is attached completely untouched (its real, professionally formatted
    PDF) rather than an AI-regenerated version that would lose that
    formatting. Guidance on which CV experiences to foreground for this
    specific posting goes in the email body as text instead, alongside the
    letter, never as an edit to the CV file itself.
    """
    subject = f"Candidature Stage AM — {posting.company} — {posting.title}"

    body_lines = []
    if letter.uncertain_elements:
        body_lines.append("⚠️ À vérifier avant l'envoi :")
        body_lines.extend(f"- {element}" for element in letter.uncertain_elements)
        body_lines.append("")
    body_lines.append(letter.letter_text)
    if letter.cv_emphasis_advice:
        body_lines.append("")
        body_lines.append("📌 CV (joint tel quel, non modifié) — à mettre en avant pour ce poste :")
        body_lines.append(letter.cv_emphasis_advice)

    mime_message = MIMEMultipart()
    mime_message["Subject"] = subject
    mime_message.attach(MIMEText("\n".join(body_lines), _charset="utf-8"))

    company_slug = _safe_filename_part(posting.company)
    letter_pdf = text_to_pdf_bytes(letter.letter_text, title=subject)
    letter_attachment = MIMEApplication(letter_pdf, _subtype="pdf")
    letter_attachment.add_header("Content-Disposition", "attachment", filename=f"Lettre de motivation - {company_slug}.pdf")
    mime_message.attach(letter_attachment)

    if cv_pdf_bytes:
        cv_attachment = MIMEApplication(cv_pdf_bytes, _subtype="pdf")
        cv_attachment.add_header("Content-Disposition", "attachment", filename="CV Clara Benhamou.pdf")
        mime_message.attach(cv_attachment)

    raw = base64.urlsafe_b64encode(mime_message.as_bytes()).decode("ascii")
    return {"message": {"raw": raw}}


class GmailDraftCreator:
    def __init__(self, gmail_service, cv_pdf_bytes: bytes | None = None):
        self._service = gmail_service
        self._cv_pdf_bytes = cv_pdf_bytes

    def create_draft(self, posting: JobPosting, letter: LetterDraft) -> str:
        body = build_draft_message(posting, letter, self._cv_pdf_bytes)
        result = self._service.users().drafts().create(userId="me", body=body).execute()
        return result.get("id", "")
