"""Bluetooth Phone widget."""

import time
import subprocess
import pygame

name = "Phone"
priority = 10

_cache = {"connected": False, "name": "", "last_check": 0}


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
                    break
        else:
            _cache["connected"] = False
    except Exception:
        _cache["connected"] = False

    return _cache["connected"]


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t

    # BT icon dot
    pygame.draw.circle(s, t["primary"], (x + 8, y + 10), 4)
    pt = hud.font_sm.render(f"BT: {_cache['name']}", True, t["text_bright"])
    s.blit(pt, (x + 18, y + 3))

    return True
