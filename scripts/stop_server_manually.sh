#!/bin/bash
# Stop Minecraft server and shutdown VPS
# Sources common functions, saves world, stops server, and shuts down the VPS

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

echo "=== Stopping Minecraft server and shutting down VPS ==="

# Save world and stop server gracefully
save_and_stop_minecraft

echo "Server stopped. VPS will shutdown in 10 seconds"
sleep 10
echo "Bye"

# Shutdown the VPS
shutdown_vps
