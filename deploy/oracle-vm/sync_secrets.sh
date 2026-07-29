#!/usr/bin/env bash
# À exécuter UNE FOIS depuis ta machine (Git Bash), puis à nouveau seulement
# si token.json est régénéré (ex. après le passage OAuth en production).
# Ces fichiers ne doivent JAMAIS être committés — voir .gitignore.
#
# Usage: ./deploy/sync_secrets.sh <user>@<ip-de-la-vm>
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <user>@<ip-de-la-vm>" >&2
  exit 1
fi

REMOTE="$1"
APP_DIR="/opt/clara-am"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ssh "$REMOTE" "mkdir -p $APP_DIR/data"

scp "$LOCAL_DIR/.env" "$LOCAL_DIR/client_secret.json" "$LOCAL_DIR/token.json" "$REMOTE:$APP_DIR/"
scp "$LOCAL_DIR/data/cv.txt" "$LOCAL_DIR/data/reference_letter.txt" "$REMOTE:$APP_DIR/data/"

# Optionnel : transfère la base existante pour ne pas reclasser (et re-consommer
# du quota Gemini sur) les offres déjà connues. Commente si tu préfères repartir
# d'une base vide sur la VM.
scp "$LOCAL_DIR/data/offres.db" "$REMOTE:$APP_DIR/data/"

echo "Secrets et données transférés vers $REMOTE:$APP_DIR"
