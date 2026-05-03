#!/usr/bin/env python3
"""Car-HUD Touch Service
Reads touch events from evdev input device and writes to /tmp/car-hud-touch.
The HUD reads this file to handle touch gestures.
"""

import os
import sys
import json
import time
import struct

TOUCH_FILE = "/tmp/car-hud-touch"
INPUT_EVENT_SIZE = struct.calcsize("llHHi")

# evdev constants
EV_KEY = 1
EV_ABS = 3
ABS_X = 0
ABS_Y = 1
BTN_TOUCH = 330

# Display mapping (touch device range → pixel range)
TOUCH_MAX_X = 2048
TOUCH_MAX_Y = 2048
DISPLAY_W = 480
DISPLAY_H = 320


def find_touch_device():
    """Find the touchscreen input device."""
    for i in range(10):
        dev = f"/dev/input/event{i}"
        try:
            name_path = f"/sys/class/input/event{i}/device/name"
            if os.path.exists(name_path):
                with open(name_path) as f:
                    name = f.read().strip()
                if "touch" in name.lower() or "chipone" in name.lower():
                    return dev
        except Exception:
            pass
    # Fallback to event0
    return "/dev/input/event0"


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def main():
    dev_path = find_touch_device()
    log(f"Touch service starting on {dev_path}")

    try:
        dev = open(dev_path, "rb")
    except PermissionError:
        log(f"Permission denied: {dev_path} — add user to input group")
        sys.exit(1)
    except FileNotFoundError:
        log(f"No touch device found at {dev_path}")
        sys.exit(1)

    log("Touch input active")

    cur_x, cur_y = 0, 0
    touch_down = False
    down_x, down_y, down_time = 0, 0, 0.0

    while True:
        try:
            data = dev.read(INPUT_EVENT_SIZE)
            if not data:
                break

            _sec, _usec, ev_type, ev_code, ev_value = struct.unpack("llHHi", data)

            if ev_type == EV_ABS:
                if ev_code == ABS_X:
                    cur_x = int(ev_value * DISPLAY_W / TOUCH_MAX_X)
                elif ev_code == ABS_Y:
                    cur_y = int(ev_value * DISPLAY_H / TOUCH_MAX_Y)

            elif ev_type == EV_KEY and ev_code == BTN_TOUCH:
                now = time.time()

                if ev_value == 1:
                    # Touch down
                    touch_down = True
                    down_x, down_y, down_time = cur_x, cur_y, now

                elif ev_value == 0 and touch_down:
                    # Touch up — determine gesture
                    touch_down = False
                    dx = cur_x - down_x
                    dy = cur_y - down_y
                    dt = now - down_time

                    gesture = "tap"
                    if dt > 1.5 and abs(dx) < 30 and abs(dy) < 30:
                        gesture = "long_press"  # held for 1.5s+ without moving
                    elif dt < 1.0 and abs(dx) > 50:
                        gesture = "swipe_right" if dx > 0 else "swipe_left"
                    elif dt < 1.0 and abs(dy) > 50:
                        gesture = "swipe_down" if dy > 0 else "swipe_up"

                    event = {
                        "gesture": gesture,
                        "x": cur_x,
                        "y": cur_y,
                        "dx": dx,
                        "dy": dy,
                        "time": now,
                    }

                    try:
                        with open(TOUCH_FILE, "w") as f:
                            json.dump(event, f)
                    except Exception:
                        pass

        except Exception as e:
            log(f"Error: {e}")
            time.sleep(1)


if __name__ == "__main__":
    main()
