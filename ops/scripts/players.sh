#!/bin/bash
# Get list of players online
# Sources common functions and retrieves player list

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

get_players
