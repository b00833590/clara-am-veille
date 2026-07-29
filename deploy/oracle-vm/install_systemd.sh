#!/usr/bin/env bash
# À exécuter SUR la VM (après provision_vm.sh et sync_secrets.sh).
set -euo pipefail

APP_DIR="/opt/clara-am"

sudo cp "$APP_DIR"/deploy/systemd/*.service "$APP_DIR"/deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload

sudo systemctl enable --now clara-am-baseline.timer
sudo systemctl enable --now clara-am-daytime.timer
sudo systemctl enable --now clara-am-validate.timer

echo "Timers installés et activés."
echo "Vérifier : systemctl list-timers 'clara-am*'"
echo "Forcer un run tout de suite pour tester : sudo systemctl start clara-am.service"
echo "Suivre les logs : journalctl -u clara-am.service -f"
