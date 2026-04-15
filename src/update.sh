#!/bin/bash
# Car-HUD OTA Update Script
# Intelligently syncs only changed/new/deleted files from GitHub.
# Downloads update first, installs on next reboot (or immediately if forced).

set -e
INSTALL_DIR="/home/chrismslist/car-hud"
REPO_URL="https://github.com/grabercn/Car-HUD"
SIGNAL_FILE="/tmp/car-hud-update-status"
STAGING_DIR="/tmp/Car-HUD-update"
BRANCH="main"

mkdir -p "$INSTALL_DIR"

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
write_status "downloading" "Downloading update..." 20

# Download latest into staging
rm -rf "$STAGING_DIR"
git clone --depth 1 "$REPO_URL" "$STAGING_DIR" 2>/dev/null

if [ ! -d "$STAGING_DIR/src" ]; then
    log "Download failed"
    write_status "failed" "Download failed" 0
    exit 1
fi

write_status "installing" "Syncing files..." 50

# --- Smart file sync: only copy changed/new, remove deleted ---
CHANGED=0
ADDED=0
DELETED=0

# Sync src/ -> install dir (py and sh files)
for f in "$STAGING_DIR"/src/*.py "$STAGING_DIR"/src/*.sh; do
    [ -f "$f" ] || continue
    fname=$(basename "$f")
    if [ -f "$INSTALL_DIR/$fname" ]; then
        if ! cmp -s "$f" "$INSTALL_DIR/$fname"; then
            cp "$f" "$INSTALL_DIR/$fname"
            log "Updated: $fname"
            CHANGED=$((CHANGED + 1))
        fi
    else
        cp "$f" "$INSTALL_DIR/$fname"
        log "Added: $fname"
        ADDED=$((ADDED + 1))
    fi
done

# Sync subdirectories (pages/, widgets/)
for subdir in pages widgets; do
    if [ -d "$STAGING_DIR/src/$subdir" ]; then
        mkdir -p "$INSTALL_DIR/$subdir"

        # Copy new/changed files
        for f in "$STAGING_DIR/src/$subdir"/*.py; do
            [ -f "$f" ] || continue
            fname=$(basename "$f")
            if [ -f "$INSTALL_DIR/$subdir/$fname" ]; then
                if ! cmp -s "$f" "$INSTALL_DIR/$subdir/$fname"; then
                    cp "$f" "$INSTALL_DIR/$subdir/$fname"
                    log "Updated: $subdir/$fname"
                    CHANGED=$((CHANGED + 1))
                fi
            else
                cp "$f" "$INSTALL_DIR/$subdir/$fname"
                log "Added: $subdir/$fname"
                ADDED=$((ADDED + 1))
            fi
        done

        # Remove files that no longer exist in repo
        for f in "$INSTALL_DIR/$subdir"/*.py; do
            [ -f "$f" ] || continue
            fname=$(basename "$f")
            if [ ! -f "$STAGING_DIR/src/$subdir/$fname" ]; then
                rm "$f"
                log "Removed: $subdir/$fname"
                DELETED=$((DELETED + 1))
            fi
        done
    fi
done

# Remove top-level py files that no longer exist in repo
for f in "$INSTALL_DIR"/*.py; do
    [ -f "$f" ] || continue
    fname=$(basename "$f")
    # Skip config/data files that aren't in the repo
    [[ "$fname" == .* ]] && continue
    if [ -f "$STAGING_DIR/src/$fname" ]; then
        : # exists in repo, already handled above
    else
        # Check if it was ever in the repo (don't delete user-created files)
        if git -C "$STAGING_DIR" log --oneline -- "src/$fname" 2>/dev/null | head -1 | grep -q .; then
            rm "$f"
            log "Removed: $fname"
            DELETED=$((DELETED + 1))
        fi
    fi
done

# Update services if changed
if [ -d "$STAGING_DIR/services" ]; then
    for f in "$STAGING_DIR"/services/*.service; do
        [ -f "$f" ] || continue
        fname=$(basename "$f")
        if ! cmp -s "$f" "/etc/systemd/system/$fname" 2>/dev/null; then
            cp "$f" "/etc/systemd/system/$fname"
            log "Service updated: $fname"
            CHANGED=$((CHANGED + 1))
        fi
    done
    systemctl daemon-reload
fi

write_status "finalizing" "Finalizing..." 90

# Save version
echo "$REMOTE_HASH" > "$INSTALL_DIR/.version"
touch "$INSTALL_DIR/.update_pending"

# Cleanup
rm -rf "$STAGING_DIR"

TOTAL=$((CHANGED + ADDED + DELETED))
DETAIL="$REMOTE_HASH: ${CHANGED} updated, ${ADDED} added, ${DELETED} removed"
log "Update complete: $DETAIL"
write_status "done" "$DETAIL" 100

# Restart services to apply
for svc in car-hud car-hud-voice car-hud-web car-hud-spotify car-hud-touch; do
    systemctl restart "$svc" 2>/dev/null || true
done

exit 0
