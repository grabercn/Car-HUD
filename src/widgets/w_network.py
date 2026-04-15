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

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=8)
    pygame.draw.rect(s, t["border_lite"], (x, y, w, h), 1, border_radius=8)

    # WiFi icon (signal bars) - vertically centered
    bx = x + 16
    by = y + h // 2 + 8
    for i in range(4):
        bh = 6 + i * 4
        bc = color if True else t["border"]
        pygame.draw.rect(s, bc, (bx + i * 8, by - bh, 6, bh), border_radius=2)

    # SSID — large
    label = ssid if state == "connected" else "USB Tethered"
    nt = hud.font_md.render(label, True, t["text_bright"])
    
    # Vertically center block of text
    text_y = y + (h - nt.get_height() - 24) // 2
    s.blit(nt, (x + 56, text_y))

    # IP and status
    info = ip if ip else state
    it = hud.font_sm.render(info, True, t["text_med"])
    s.blit(it, (x + 56, text_y + nt.get_height() + 4))

    return True
