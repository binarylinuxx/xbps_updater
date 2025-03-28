#!/usr/bin/env bash

# Improved installer script for xbps_updater

# Configuration
APP_NAME="XBPS Updater"
VERSION="1.0"
ICON_FILE="upd.svg"
DESKTOP_FILE="xbps_updater.desktop"
SCRIPT_FILE="xbps_updater.py"
SERVICE_FILE="run"
CLI="xbps_updater"

# Installation paths
INSTALL_DIR="/usr/local/bin"
ICON_DIR="/usr/share/icons"
DESKTOP_DIR="/usr/share/applications"
SERVICE_DIR="/etc/sv/xbps-updater"

# services
SERVICE="xbps-updater"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo -e "======> ${RED}Error: This script must be run as root.${NC}" >&2
        echo -e "======> Please run with ${YELLOW}sudo${NC} or as ${YELLOW}root${NC}."
        exit 1
    fi
}

# Check if files exist
check_files() {
    local missing_files=()
    
    [ ! -f "$SCRIPT_FILE" ] && missing_files+=("$SCRIPT_FILE")
    [ ! -f "$ICON_FILE" ] && missing_files+=("$ICON_FILE")
    [ ! -f "$DESKTOP_FILE" ] && missing_files+=("$DESKTOP_FILE")
    [ ! -f "$SERVICE_FILE" ] && missing_files+=("$SERVICE_FILE")
    [ ! -f "$CLI" ] && missing_files+=("$CLI")
    
    if [ ${#missing_files[@]} -gt 0 ]; then
        echo -e "${RED}Error: Missing required files:${NC}" >&2
        for file in "${missing_files[@]}"; do
            echo -e " - ${YELLOW}$file${NC}"
        done
        exit 1
    fi
}

# Install files
install_files() {
    echo -e "${GREEN}Installing $APP_NAME $VERSION...${NC}"
    
    # Create directories if they don't exist
    mkdir -p "$INSTALL_DIR"
    mkdir -p "$ICON_DIR"
    mkdir -p "$DESKTOP_DIR"
    
    # Install script
    echo -e "Installing script to ${YELLOW}${INSTALL_DIR}/${SCRIPT_FILE}${NC}"
    cp "$SCRIPT_FILE" "$INSTALL_DIR/"
    chmod 755 "$INSTALL_DIR/$SCRIPT_FILE"
    
    # Install icon
    echo -e "Installing icon to ${YELLOW}${ICON_DIR}/${ICON_FILE}${NC}"
    cp "$ICON_FILE" "$ICON_DIR/"
    
    # Install desktop file (with corrected paths)
    echo -e "Installing desktop file to ${YELLOW}${DESKTOP_DIR}/${DESKTOP_FILE}${NC}"
    sed "s|Exec=python /usr/bin/xbps_updater.py|Exec=python ${INSTALL_DIR}/${SCRIPT_FILE}|g" "$DESKTOP_FILE" | \
    sed "s|Icon=/usr/share/upd.svg|Icon=${ICON_DIR}/${ICON_FILE}|g" > temp.desktop
    cp temp.desktop "$DESKTOP_DIR/$DESKTOP_FILE"
    rm temp.desktop
    
    # Update desktop database
    if command -v update-desktop-database >/dev/null; then
        update-desktop-database "$DESKTOP_DIR"
    fi
}

install_service_and_cli() {
    echo -e "Installing CLI to ${YELLOW}/usr/bin/${CLI}${NC}"
    cp "$CLI" "/usr/bin/"
    chmod +x "/usr/bin/$CLI"
    
    echo -e "Installing service to ${YELLOW}${SERVICE_DIR}${NC}"
    mkdir -p "$SERVICE_DIR"
    mkdir -p "$SERVICE_DIR/log"
    
    # Install service run file
    cp "$SERVICE_FILE" "$SERVICE_DIR/run"
    chmod +x "$SERVICE_DIR/run"
    
    # Create log run file
    echo '#!/bin/sh' > "$SERVICE_DIR/log/run"
    echo 'exec svlogd -tt ./main' >> "$SERVICE_DIR/log/run"
    chmod +x "$SERVICE_DIR/log/run"
    
    # Enable the service
    if [ ! -L "/var/service/$SERVICE" ]; then
        ln -s "$SERVICE_DIR" "/var/service/"
    fi
    
    # Start the service
    sv up "$SERVICE"
}

# Main function
main() {
    echo -e "\n===> ${APP_NAME} Installer"
    check_root
    check_files
    install_files
    install_service_and_cli
    
    echo -e "\n${GREEN}Installation completed successfully!${NC}"
    echo -e "You can now run ${YELLOW}${INSTALL_DIR}/${SCRIPT_FILE}${NC} or find ${APP_NAME} in your application menu."
}

main
