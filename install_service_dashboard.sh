#!/usr/bin/env bash
# install_service_dashboard.sh
# Installs the k8s-service-dashboard Flask app as a systemd service on port 80
# Runs as root - low traffic internal tool

set -euo pipefail

# ================= CONFIGURATION =================
APP_NAME="k8s-service-dashboard"
APP_DIR="/opt/${APP_NAME}"
VENV_DIR="${APP_DIR}/venv"
APP_USER="root"
APP_GROUP="root"

PYTHON_BIN="/usr/bin/python3"
PORT=80
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

# ================= CHECKS =================
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}This script must be run as root${NC}" >&2
    exit 1
fi

command -v python3 >/dev/null 2>&1 || { echo -e "${RED}python3 is required${NC}"; exit 1; }

# ================= SETUP DIRECTORY =================
echo "Creating application directory: ${APP_DIR}"
mkdir -p "${APP_DIR}"
mkdir -p "${APP_DIR}/templates"
cp code/app.py "${APP_DIR}/"
cp code/requirements.txt "${APP_DIR}/"
cp code/templates/index.html "${APP_DIR}/templates/"

# ================= VIRTUAL ENVIRONMENT =================
echo "Setting up virtual environment..."
if [[ ! -d "${VENV_DIR}" ]]; then
    ${PYTHON_BIN} -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r "${APP_DIR}/requirements.txt" || pip install flask kubernetes
deactivate

# ================= SYSTEMD SERVICE =================
echo "Creating systemd service: ${SERVICE_FILE}"

cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Kubernetes External Services Dashboard (Flask)
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${APP_DIR}
Environment="PATH=${VENV_DIR}/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=${VENV_DIR}/bin/python ${APP_DIR}/app.py

Restart=always
RestartSec=10
StartLimitInterval=60s
StartLimitBurst=3
KillMode=mixed
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target
EOF

chmod 644 "${SERVICE_FILE}"

# ================= ACTIVATE SERVICE =================
echo "Reloading systemd..."
systemctl daemon-reload

echo "Enabling service..."
systemctl enable "${APP_NAME}.service"

echo "Starting service..."
systemctl start "${APP_NAME}.service"

echo -e "\n${GREEN}Installation complete!${NC}"
echo "Dashboard should be available at: http://<server-ip>/ (port 80)"
echo ""
echo "Status:"
systemctl status "${APP_NAME}.service" --no-pager --lines=8
echo ""
echo "Logs: journalctl -u ${APP_NAME} -f"