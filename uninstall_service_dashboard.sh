#!/usr/bin/env bash
# uninstall_service_dashboard.sh
# Removes the k8s-service-dashboard Flask app and systemd service

set -euo pipefail

# ================= CONFIGURATION =================
APP_NAME="k8s-service-dashboard"
APP_DIR="/opt/${APP_NAME}"
VENV_DIR="${APP_DIR}/venv"
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

# ================= STOP AND DISABLE SERVICE =================
if systemctl is-active --quiet "${APP_NAME}.service"; then
    echo "Stopping service..."
    systemctl stop "${APP_NAME}.service"
fi

if systemctl is-enabled --quiet "${APP_NAME}.service"; then
    echo "Disabling service..."
    systemctl disable "${APP_NAME}.service"
fi

# ================= REMOVE SERVICE FILE =================
if [[ -f "${SERVICE_FILE}" ]]; then
    echo "Removing systemd service file: ${SERVICE_FILE}"
    rm -f "${SERVICE_FILE}"
    systemctl daemon-reload
fi

# ================= REMOVE APPLICATION DIRECTORY =================
if [[ -d "${APP_DIR}" ]]; then
    echo "Removing application directory: ${APP_DIR}"
    rm -rf "${APP_DIR}"
fi

echo -e "\n${GREEN}Uninstallation complete!${NC}"
echo "The k8s-service-dashboard has been removed."