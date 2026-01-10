#!/bin/bash
# Reboot Minecraft server and VPS
# Sources common functions, saves world, stops server, and reboots the VPS

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

echo "=== Stopping Minecraft server and rebooting VPS ==="

# Save world and stop server gracefully
save_and_stop_minecraft

echo "Server stopped. VPS will reboot in 10 seconds"
sleep 10
echo "Bye"

# Reboot the VPS
reboot_vps
