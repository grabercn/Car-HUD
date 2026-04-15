"""Bluetooth Phone widget — shows connected device info."""

import time
import subprocess
import pygame

name = "Phone"
priority = 10

_cache = {"connected": False, "name": "", "mac": "", "battery": "", "last_check": 0}


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
