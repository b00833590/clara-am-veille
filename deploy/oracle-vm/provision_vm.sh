#!/usr/bin/env bash
# À exécuter UNE FOIS sur la VM fraîche (via ssh), après sync_code.sh.
# Suppose Ubuntu 22.04/24.04 (image par défaut Oracle Cloud Always Free).
set -euo pipefail

APP_DIR="/opt/clara-am"

sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip

sudo mkdir -p "$APP_DIR"
sudo chown "$(whoami)":"$(whoami)" "$APP_DIR"

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

# Playwright a besoin de ses propres dépendances système (polices, libnss...)
# en plus du binaire Chromium — --with-deps installe les deux.
"$APP_DIR/.venv/bin/python" -m playwright install --with-deps chromium

# Les horaires des timers (8h-22h, toutes les 3h) sont pensés en heure de
# Paris — sans ça la VM (par défaut en UTC) déclencherait 2h trop tôt/tard.
sudo timedatectl set-timezone Europe/Paris

mkdir -p "$APP_DIR/logs" "$APP_DIR/data"
chmod +x "$APP_DIR/deploy/run.sh" "$APP_DIR/deploy/install_systemd.sh"

echo "Provisioning terminé."
echo "Étapes suivantes : sync_secrets.sh (depuis ta machine), puis deploy/install_systemd.sh (sur la VM)."
