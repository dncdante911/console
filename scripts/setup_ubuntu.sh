#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-panel}" # panel | license
INSTALL_DIR="${INSTALL_DIR:-/opt/minihost}"
PANEL_PORT="${PANEL_PORT:-8088}"
LICENSE_PORT="${LICENSE_PORT:-8099}"
LICENSE_API_TOKEN="${LICENSE_API_TOKEN:-change-me}"

sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx postfix dovecot-imapd dovecot-pop3d

sudo mkdir -p "$INSTALL_DIR"
sudo rsync -a --delete ./ "$INSTALL_DIR/"
cd "$INSTALL_DIR"

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

if [[ "$MODE" == "panel" ]]; then
  sudo tee /etc/systemd/system/minihost-panel.service >/dev/null <<SERVICE
[Unit]
Description=MiniHost Panel
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment=PANEL_SERVER_IP=$(hostname -I | awk '{print $1}')
ExecStart=$INSTALL_DIR/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port $PANEL_PORT
Restart=always

[Install]
WantedBy=multi-user.target
SERVICE

  sudo systemctl daemon-reload
  sudo systemctl enable --now minihost-panel
  echo "Panel started: http://SERVER_IP:$PANEL_PORT"
fi

if [[ "$MODE" == "license" ]]; then
  sudo tee /etc/systemd/system/minihost-license.service >/dev/null <<SERVICE
[Unit]
Description=MiniHost License Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment=LICENSE_API_TOKEN=$LICENSE_API_TOKEN
ExecStart=$INSTALL_DIR/.venv/bin/uvicorn license_server.main:app --host 0.0.0.0 --port $LICENSE_PORT
Restart=always

[Install]
WantedBy=multi-user.target
SERVICE

  sudo systemctl daemon-reload
  sudo systemctl enable --now minihost-license
  echo "License server started: http://SERVER_IP:$LICENSE_PORT"
fi
