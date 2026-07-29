import base64
from email.mime.text import MIMEText

from src.models import JobPosting

CATEGORY_LABELS = {"A": "AM prioritaire"}


def build_notification_message(posting: JobPosting, recipient_email: str) -> dict:
    category_label = CATEGORY_LABELS.get(posting.category, "à classer")
    subject = f"Nouvelle offre stage AM — {posting.company} — {posting.title}"
    body_lines = [
        f"Entreprise : {posting.company}",
        f"Poste : {posting.title}",
        f"Catégorie : {category_label}",
    ]
    if posting.to_verify:
        reason = f" — {posting.classification_reason}" if posting.classification_reason else ""
        body_lines.append(f"À vérifier : classification ambiguë, à relire manuellement{reason}.")
    if posting.location:
        body_lines.append(f"Lieu : {posting.location}")
    body_lines.append(f"Lien : {posting.url}")

    mime_message = MIMEText("\n".join(body_lines), _charset="utf-8")
    mime_message["To"] = recipient_email
    mime_message["Subject"] = subject

    raw = base64.urlsafe_b64encode(mime_message.as_bytes()).decode("ascii")
    return {"raw": raw}


class GmailNotifier:
    def __init__(self, gmail_service, recipient_email: str):
        self._service = gmail_service
        self._recipient_email = recipient_email

    def notify_new_posting(self, posting: JobPosting) -> None:
        message = build_notification_message(posting, self._recipient_email)
        self._service.users().messages().send(userId="me", body=message).execute()
