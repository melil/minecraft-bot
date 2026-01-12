#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

echo "=== Saving world and stopping Minecraft ==="
save_and_stop_minecraft

echo "Minecraft stopped. VPS shutdown will be handled via API"