from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# gmail.send : notifications de nouvelles offres (Phase 2)
# gmail.compose : dépôt des brouillons de lettres (Phase 3)
# spreadsheets : synchronisation du tableau de suivi (Phase 4)
# Demandés ensemble pour que Clara n'ait à passer par l'écran de consentement
# qu'une seule fois. Les trois scopes doivent être ajoutés côté Google Auth
# platform → Data Access avant le premier lancement (voir CLAUDE.md).
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/spreadsheets",
]


def _get_credentials(client_secret_path: Path, token_path: Path) -> Credentials:
    creds = _load_credentials(token_path)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return creds


def get_gmail_service(client_secret_path: Path, token_path: Path):
    return build("gmail", "v1", credentials=_get_credentials(client_secret_path, token_path))


def get_sheets_service(client_secret_path: Path, token_path: Path):
    return build("sheets", "v4", credentials=_get_credentials(client_secret_path, token_path))


def _load_credentials(token_path: Path) -> Credentials | None:
    if not token_path.exists():
        return None
    return Credentials.from_authorized_user_file(str(token_path), SCOPES)
