#!/bin/bash
# Car-HUD OTA Update Script
# Checks GitHub for updates, downloads, replaces files, restarts services.
# Called on boot by car-hud-updater.service or manually.

set -e
INSTALL_DIR="/home/chrismslist/northstar"
REPO_URL="https://github.com/grabercn/Car-HUD"
SIGNAL_FILE="/tmp/car-hud-update-status"
BRANCH="main"

write_status() {
    echo "{\"status\":\"$1\",\"detail\":\"$2\",\"progress\":$3,\"time\":$(date +%s)}" > "$SIGNAL_FILE"
}

log() {
    echo "[$(date +%H:%M:%S)] $1"
}

# Check network
if ! ping -c 1 -W 3 8.8.8.8 > /dev/null 2>&1; then
    log "No network — skipping update"
    exit 0
fi

write_status "checking" "Checking for updates..." 10

# Get latest commit hash from GitHub
REMOTE_HASH=$(curl -s "https://api.github.com/repos/grabercn/Car-HUD/commits/$BRANCH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha','')[:8])" 2>/dev/null)

# Get local hash
LOCAL_HASH=""
if [ -f "$INSTALL_DIR/.version" ]; then
    LOCAL_HASH=$(cat "$INSTALL_DIR/.version")
fi

if [ "$REMOTE_HASH" = "$LOCAL_HASH" ] || [ -z "$REMOTE_HASH" ]; then
    log "Already up to date ($LOCAL_HASH)"
    write_status "current" "Up to date" 100
    exit 0
fi

log "Update available: $LOCAL_HASH -> $REMOTE_HASH"
write_status "downloading" "Downloading update..." 30

# Download latest
cd /tmp
rm -rf Car-HUD-update
git clone --depth 1 "$REPO_URL" Car-HUD-update 2>/dev/null

if [ ! -d /tmp/Car-HUD-update/src ]; then
    log "Download failed"
    write_status "failed" "Download failed" 0
    exit 1
fi

write_status "installing" "Installing update..." 60

# Stop services
for svc in northstar-hud car-hud-voice car-hud-web car-hud-music; do
    systemctl stop "$svc" 2>/dev/null || true
done

# Backup current
cp -r "$INSTALL_DIR"/*.py "$INSTALL_DIR/.backup_$(date +%Y%m%d)" 2>/dev/null || true

# Copy new files
cp /tmp/Car-HUD-update/src/*.py "$INSTALL_DIR/"

# Update services if changed
if [ -d /tmp/Car-HUD-update/services ]; then
    cp /tmp/Car-HUD-update/services/*.service /etc/systemd/system/ 2>/dev/null || true
    systemctl daemon-reload
fi

write_status "restarting" "Restarting services..." 80

# Save version
echo "$REMOTE_HASH" > "$INSTALL_DIR/.version"

# Restart
for svc in northstar-hud car-hud-voice car-hud-web car-hud-obd car-hud-wifi car-hud-dashcam car-hud-music; do
    systemctl start "$svc" 2>/dev/null || true
done

# Cleanup
rm -rf /tmp/Car-HUD-update

write_status "done" "Updated to $REMOTE_HASH" 100
log "Update complete: $REMOTE_HASH"
