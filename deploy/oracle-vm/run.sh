#!/usr/bin/env bash
# Équivalent Linux de run.ps1 — appelé par les units systemd, jamais directement
# par cron, pour garantir que stdout/stderr sont toujours capturés (le run
# manuel du 28/07 a perdu son message d'erreur faute de redirection : voir
# CLAUDE.md, section Amundi/Lazard).
set -euo pipefail

APP_DIR="/opt/clara-am"
cd "$APP_DIR"

LOG_DIR="$APP_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/run_$(date +%Y%m%d).log"
SCRIPT="${1:-main.py}"

{
  echo "=== Run started at $(date '+%Y-%m-%d %H:%M:%S') ($SCRIPT) ==="
  "$APP_DIR/.venv/bin/python" "$APP_DIR/$SCRIPT"
  echo "=== Run finished at $(date '+%Y-%m-%d %H:%M:%S') ==="
} >> "$LOG_FILE" 2>&1
