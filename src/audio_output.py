"""Intelligent audio output selection.
Priority: USB audio card > HDMI (if connected) > Pi headphones.
Caches the result, re-checks every 30 seconds.
"""
import os
import time
import subprocess

_cached_dev = None
_cache_time = 0
CACHE_TTL = 30

def get_best_output():
    global _cached_dev, _cache_time
    now = time.time()
    if _cached_dev and now - _cache_time < CACHE_TTL:
        return _cached_dev

    # Scan cards
    usb_card = None
    hdmi_card = None
    headphone_card = None

    for c in range(6):
        p = f"/proc/asound/card{c}/id"
        if os.path.exists(p):
            with open(p) as f:
                name = f.read().strip()
            if name in ("Audio", "Card"):
                usb_card = c
            elif name == "vc4hdmi":
                # Only use HDMI if display is connected
                try:
                    with open("/sys/class/drm/card0-HDMI-A-1/status") as f:
                        if "connected" in f.read():
                            hdmi_card = c
                except Exception:
                    pass
            elif name == "Headphones":
                headphone_card = c

    # Priority: USB > HDMI > Headphones
    if usb_card is not None:
        _cached_dev = f"dmix:{usb_card}"
    elif hdmi_card is not None:
        _cached_dev = f"plughw:{hdmi_card},0"
    elif headphone_card is not None:
        _cached_dev = f"plughw:{headphone_card},0"
    else:
        _cached_dev = "default"

    _cache_time = now
    return _cached_dev

def play(filepath):
    try:
        dev = get_best_output()
        subprocess.Popen(["aplay", "-D", dev, filepath],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
