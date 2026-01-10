#!/bin/bash
# Common functions for Minecraft server management scripts
# Source this file in other scripts to use the functions

# RCON Configuration
RCON_HOST="${RCON_HOST:-127.0.0.1}"
RCON_PORT="${RCON_PORT:-25575}"
RCON_PASSWORD="${RCON_PASSWORD:-SuperPassword228}"

# Server Directory
SERVER_DIR="${SERVER_DIR:-/root/freshcraft_industrial_server}"

# Save the Minecraft world
save_world() {
    echo "Saving Minecraft world..."
    if mcrcon -H "$RCON_HOST" -P "$RCON_PORT" -p "$RCON_PASSWORD" save-all >/dev/null 2>&1; then
        echo "World saved successfully"
        return 0
    else
        echo "Warning: Failed to save world (server might not be running)"
        return 1
    fi
}

# Stop the Minecraft server via RCON
stop_minecraft() {
    echo "Stopping Minecraft server..."
    if mcrcon -H "$RCON_HOST" -P "$RCON_PORT" -p "$RCON_PASSWORD" stop >/dev/null 2>&1; then
        echo "Stop command sent to Minecraft server"
        return 0
    else
        echo "Warning: Failed to send stop command (server might not be running)"
        return 1
    fi
}

# Start the Minecraft server
start_minecraft() {
    echo "Starting Minecraft server..."
    if [ ! -d "$SERVER_DIR" ]; then
        echo "Error: Server directory not found: $SERVER_DIR"
        return 1
    fi
    
    cd "$SERVER_DIR" || exit 1
    exec ./run.sh
}

# Get list of players online
get_players() {
    mcrcon -H "$RCON_HOST" -P "$RCON_PORT" -p "$RCON_PASSWORD" list 2>/dev/null
}

# Save and stop Minecraft server gracefully
save_and_stop_minecraft() {
    save_world
    sleep 10
    stop_minecraft
    sleep 20
}

# Shutdown the VPS
shutdown_vps() {
    echo "Shutting down VPS..."
    shutdown -h now
}

# Reboot the VPS
reboot_vps() {
    echo "Rebooting VPS..."
    reboot
}
