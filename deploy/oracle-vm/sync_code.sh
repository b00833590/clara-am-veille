#!/usr/bin/env bash
# À exécuter depuis ta machine (Git Bash) pour envoyer/mettre à jour le CODE
# sur la VM — jamais les secrets ni les données (voir sync_secrets.sh).
# Sans risque à relancer autant de fois que nécessaire : ne touche jamais à
# data/, .venv/ ni logs/ côté VM.
#
# Usage: ./deploy/sync_code.sh <user>@<ip-de-la-vm>
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <user>@<ip-de-la-vm>" >&2
  exit 1
fi

REMOTE="$1"
APP_DIR="/opt/clara-am"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ssh "$REMOTE" "sudo mkdir -p $APP_DIR && sudo chown \$(whoami):\$(whoami) $APP_DIR"

scp -r \
  "$LOCAL_DIR/main.py" \
  "$LOCAL_DIR/requirements.txt" \
  "$LOCAL_DIR/src" \
  "$LOCAL_DIR/scripts" \
  "$LOCAL_DIR/deploy" \
  "$REMOTE:$APP_DIR/"

echo "Code synchronisé vers $REMOTE:$APP_DIR"
