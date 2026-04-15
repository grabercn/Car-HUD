"""Network / WiFi widget."""

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
    label = f"WiFi: {ssid}" if state == "connected" else "USB Tethered"

    pygame.draw.circle(s, color, (x + 8, y + 10), 4)
    nt = hud.font_sm.render(label, True, t["text_bright"])
    s.blit(nt, (x + 18, y + 3))

    if ip:
        it = hud.font_xs.render(ip, True, t["text_dim"])
        s.blit(it, (x + 18, y + 20))

    return True
