#!/usr/bin/env bash

# Configuration
PREFIX="${PREFIX:-/usr/local}"
DESTDIR="${DESTDIR:-}"
APP_NAME="XBPS Updater"
VERSION="1.0"

# Installation paths
INSTALL_DIR="${DESTDIR}${PREFIX}/bin"
ICON_DIR="${DESTDIR}${PREFIX}/share/icons"
DESKTOP_DIR="${DESTDIR}${PREFIX}/share/applications"
SERVICE_DIR="${DESTDIR}/etc/sv/xbps-updater"
SERVICE_TO_INSTALL="polkit polkit-devel"
PKGS="python3 python3-gobject"

# Files
SCRIPT_FILE="xbps_updater.py"
ICON_FILE="upd.svg"
DESKTOP_FILE="xbps_updater.desktop"
SERVICE_FILE="run"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

install_files() {
    echo -e "${GREEN}Installing ${APP_NAME} ${VERSION}${NC}"
    
    # Create directories
    mkdir -p "${INSTALL_DIR}" "${ICON_DIR}" "${DESKTOP_DIR}" "${SERVICE_DIR}"
    
    # Install main script
    echo "Installing main script to ${INSTALL_DIR}/${SCRIPT_FILE}"
    install -m755 "${SCRIPT_FILE}" "${INSTALL_DIR}/"
    
    # Install icon
    echo "Installing icon to ${ICON_DIR}/${ICON_FILE}"
    install -m644 "${ICON_FILE}" "${ICON_DIR}/"
    
    # Install desktop file
    echo "Installing desktop file to ${DESKTOP_DIR}/${DESKTOP_FILE}"
    sed -e "s|Exec=.*|Exec=${PREFIX}/bin/${SCRIPT_FILE}|" \
        -e "s|Icon=.*|Icon=${PREFIX}/share/icons/${ICON_FILE}|" \
        "${DESKTOP_FILE}" > "${DESKTOP_DIR}/${DESKTOP_FILE}"
    
    # Install service
    echo "Installing service to ${SERVICE_DIR}"
    install -m755 "${SERVICE_FILE}" "${SERVICE_DIR}/run"
    mkdir -p "${SERVICE_DIR}/log"
    echo '#!/bin/sh' > "${SERVICE_DIR}/log/run"
    echo 'exec svlogd -tt ./main' >> "${SERVICE_DIR}/log/run"
    chmod +x "${SERVICE_DIR}/log/run"
    sudo xbps-install -S $SERVICE_TO_INSTALL $PKGS
    sudo ln -s /etc/sv/polkitd /var/service
    sudo sv up polkitd
    
    # Update desktop database
    if command -v update-desktop-database >/dev/null; then
        update-desktop-database "${DESKTOP_DIR}"
    fi
}

main() {
    # Check dependencies
    command -v python3 >/dev/null || { echo "${RED}Error: python3 not found${NC}"; exit 1; }
    command -v xbps-install >/dev/null || { echo "${RED}Error: xbps-install not found${NC}"; exit 1; }
    
    install_files
    
    echo -e "\n${GREEN}Installation complete!${NC}"
    echo "You can now run: ${PREFIX}/bin/${SCRIPT_FILE}"
}

main "$@"
