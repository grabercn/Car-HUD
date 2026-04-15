#!/bin/bash
# BT auto-connect: continuously try to connect to last paired phone
rfkill unblock bluetooth
sleep 2
bluetoothctl power on
sleep 1
bluetoothctl discoverable on
bluetoothctl pairable on

PAIRED_FILE="/home/chrismslist/car-hud/.paired_phone"

while true; do
    # Check if already connected
    INFO=$(bluetoothctl info 2>/dev/null)
    if echo "$INFO" | grep -q "Connected: yes"; then
        # Connected — save this phone
        MAC=$(echo "$INFO" | head -1 | grep -oE '[0-9A-F:]{17}')
        NAME=$(echo "$INFO" | grep 'Name:' | head -1 | sed 's/.*Name: //')
        if [ -n "$MAC" ]; then
            python3 -c "import json; json.dump({'mac':'$MAC','name':'$NAME'},open('$PAIRED_FILE','w'))" 2>/dev/null
            bluetoothctl trust "$MAC" 2>/dev/null
        fi
        sleep 30
    else
        # Not connected — try to connect to saved phone
        PHONE=$(python3 -c "import json; print(json.load(open('$PAIRED_FILE')).get('mac',''))" 2>/dev/null)
        if [ -n "$PHONE" ]; then
            bluetoothctl connect "$PHONE" 2>/dev/null
        fi
        # Keep discoverable for new pairings
        bluetoothctl discoverable on 2>/dev/null
        sleep 15
    fi
done
