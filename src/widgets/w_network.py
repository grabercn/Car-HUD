"""Network / WiFi widget — connection details."""

import json
import pygame

name = "Network"
priority = 20


def is_active(hud, music):
    try:
        with open("/tmp/car-hud-wifi-data") as f:
            wd = json.load(f)
        return wd.get("state") in ("connected", "tethered")
    except Exception:
        return False


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t

    try:
        with open("/tmp/car-hud-wifi-data") as f:
            wd = json.load(f)
    except Exception:
        return False

    state = wd.get("state", "")
    ssid = wd.get("ssid", "")
    ip = wd.get("ip", "")

    color = t["primary"] if state == "connected" else (0, 180, 85)

    # WiFi icon (signal bars)
    bx = x + 4
    for i in range(4):
        bh = 4 + i * 4
        bc = color if True else t["border"]
        pygame.draw.rect(s, bc, (bx + i * 6, y + 20 - bh, 4, bh), border_radius=1)

    # SSID — large
    label = ssid if state == "connected" else "USB Tethered"
    nt = hud.font_md.render(label, True, t["text_bright"])
    s.blit(nt, (x + 32, y + 2))

    # IP and status
    info = ip if ip else state
    it = hud.font_sm.render(info, True, t["text_med"])
    s.blit(it, (x + 32, y + 22))

    return True
