#!/bin/bash
# Called by librespot on playback events
# Writes current track to /tmp/car-hud-librespot-event
# Environment vars set by librespot:
#   PLAYER_EVENT: changed, started, stopped, paused, playing, volume_changed
#   TRACK_ID, OLD_TRACK_ID, DURATION_MS, POSITION_MS

EVENT_FILE="/tmp/car-hud-librespot-event"

case "$PLAYER_EVENT" in
    changed|started|playing)
        cat > "$EVENT_FILE" << EOF
{"event":"$PLAYER_EVENT","track_id":"${TRACK_ID:-}","duration_ms":${DURATION_MS:-0},"position_ms":${POSITION_MS:-0},"time":$(date +%s)}
EOF
        ;;
    paused|stopped)
        cat > "$EVENT_FILE" << EOF
{"event":"$PLAYER_EVENT","track_id":"${TRACK_ID:-}","duration_ms":${DURATION_MS:-0},"position_ms":${POSITION_MS:-0},"time":$(date +%s)}
EOF
        ;;
esac
