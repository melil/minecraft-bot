#!/bin/bash
# Start Minecraft server manually
# Sources common functions and starts the server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

start_minecraft
