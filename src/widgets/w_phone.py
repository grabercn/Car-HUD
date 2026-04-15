"""Bluetooth Phone widget — shows connected device info."""

import time
import subprocess
import pygame

name = "Phone"
priority = 20

_cache = {"connected": False, "name": "", "mac": "", "battery": "", "last_check": 0}
_was_connected = False
_connect_time = 0


def is_active(hud, music):
    now = time.time()
    if now - _cache["last_check"] < 5:
        return _cache["connected"]

    _cache["last_check"] = now
    try:
        bt = subprocess.run(["bluetoothctl", "info"],
                            capture_output=True, text=True, timeout=3)
        if "Connected: yes" in bt.stdout:
            _cache["connected"] = True
            for line in bt.stdout.splitlines():
                if "Name:" in line:
                    _cache["name"] = line.split("Name:")[1].strip()
                elif "Battery" in line and "%" in line:
                    _cache["battery"] = line.strip()
        else:
            _cache["connected"] = False
    except Exception:
        _cache["connected"] = False

    return _cache["connected"]


def urgency(hud, music):
    """Promote when phone just connected (10 seconds)."""
    global _was_connected, _connect_time
    connected = _cache["connected"]
    if connected and not _was_connected:
        _connect_time = time.time()
    _was_connected = connected
    if connected and time.time() - _connect_time < 10:
        return -80  # just connected — show prominently
    return 0


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t

    # Phone icon (filled circle)
    pygame.draw.circle(s, t["primary"], (x + 10, y + 12), 6)
    pygame.draw.circle(s, t["bg"], (x + 10, y + 12), 4)
    pygame.draw.circle(s, t["primary"], (x + 10, y + 12), 2)

    # Name — large
    nt = hud.font_md.render(_cache["name"], True, t["text_bright"])
    s.blit(nt, (x + 22, y + 2))

    # Status line
    status = "Connected via Bluetooth"
    st = hud.font_sm.render(status, True, t["text_med"])
    s.blit(st, (x + 22, y + 22))

    return True
