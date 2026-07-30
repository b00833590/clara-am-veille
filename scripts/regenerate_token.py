"""Déclenche uniquement le consentement OAuth (Gmail + Sheets, un seul écran)
pour régénérer token.json en mode 'In production' — ne lance aucune partie
du pipeline (pas de scraping, pas de classification, pas de notification).
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.notifications.gmail_auth import get_gmail_service, get_sheets_service  # noqa: E402

CLIENT_SECRET_PATH = ROOT / "client_secret.json"
TOKEN_PATH = ROOT / "token.json"


def main() -> None:
    load_dotenv(ROOT / ".env")
    get_gmail_service(CLIENT_SECRET_PATH, TOKEN_PATH)
    get_sheets_service(CLIENT_SECRET_PATH, TOKEN_PATH)
    print(f"OK — token régénéré avec les scopes Gmail + Sheets : {TOKEN_PATH}")


if __name__ == "__main__":
    main()
