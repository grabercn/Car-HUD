#!/bin/bash
# BT auto-connect: connect to last paired PHONE (not OBD adapter)
rfkill unblock bluetooth
sleep 2
bluetoothctl power on
sleep 1
bluetoothctl discoverable on
bluetoothctl pairable on

PAIRED_FILE="/home/chrismslist/car-hud/.paired_phone"
# Known OBD adapter names to exclude
OBD_NAMES="vlink|obd|elm327|vgate|icar"

while true; do
    # Check all connected devices, find actual phones
    DEVICES=$(bluetoothctl devices Connected 2>/dev/null)
    PHONE_FOUND=""

    while IFS= read -r line; do
        MAC=$(echo "$line" | grep -oE '[0-9A-F:]{17}')
        [ -z "$MAC" ] && continue

        INFO=$(bluetoothctl info "$MAC" 2>/dev/null)
        NAME=$(echo "$INFO" | grep 'Name:' | head -1 | sed 's/.*Name: //')
        ICON=$(echo "$INFO" | grep 'Icon:' | head -1 | sed 's/.*Icon: //')

        # Skip OBD adapters (by name or icon)
        if echo "$NAME" | grep -iqE "$OBD_NAMES"; then
            continue
        fi

        # Only save as phone if it looks like a phone
        if echo "$ICON" | grep -q "phone"; then
            PHONE_FOUND="$MAC"
            python3 -c "import json; json.dump({'mac':'$MAC','name':'$NAME'},open('$PAIRED_FILE','w'))" 2>/dev/null
            bluetoothctl trust "$MAC" 2>/dev/null
            break
        fi
    done <<< "$DEVICES"

    if [ -n "$PHONE_FOUND" ]; then
        sleep 30
    else
        # Not connected — try to connect to saved phone
        PHONE=$(python3 -c "import json; print(json.load(open('$PAIRED_FILE')).get('mac',''))" 2>/dev/null)
        if [ -n "$PHONE" ]; then
            bluetoothctl connect "$PHONE" 2>/dev/null
        fi
        bluetoothctl discoverable on 2>/dev/null
        sleep 15
    fi
done
