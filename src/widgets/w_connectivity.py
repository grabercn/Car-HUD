"""Connectivity widget — WiFi + Bluetooth unified."""

import json
import time
import subprocess
import pygame

name = "Connectivity"
priority = 15

_bt_cache = {"connected": False, "name": "", "last_check": 0}


def is_active(hud, music):
    wifi = False
    try:
        with open("/tmp/car-hud-wifi-data") as f:
            wd = json.load(f)
        wifi = wd.get("state") in ("connected", "tethered")
    except Exception:
        pass
    return wifi or _check_bt()


def _check_bt():
    now = time.time()
    if now - _bt_cache["last_check"] < 5:
        return _bt_cache["connected"]
    _bt_cache["last_check"] = now
    try:
        bt = subprocess.run(["bluetoothctl", "info"],
                            capture_output=True, text=True, timeout=3)
        if "Connected: yes" in bt.stdout:
            _bt_cache["connected"] = True
            for line in bt.stdout.splitlines():
                if "Name:" in line:
                    _bt_cache["name"] = line.split("Name:")[1].strip()
                    break
        else:
            _bt_cache["connected"] = False
    except Exception:
        _bt_cache["connected"] = False
    return _bt_cache["connected"]


def urgency(hud, music):
    return 0


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    mid = w // 2
    pad = 10

    # ── Left: WiFi ──
    wifi_ok = False
    try:
        with open("/tmp/car-hud-wifi-data") as f:
            wd = json.load(f)
        state = wd.get("state", "")
        ssid = wd.get("ssid", "")
        ip = wd.get("ip", "")
        wifi_ok = state in ("connected", "tethered")
    except Exception:
        state, ssid, ip = "", "", ""

    color = t["primary"] if wifi_ok else t["text_dim"]
    label = ssid[:14] if wifi_ok and state == "connected" else "Tethered" if state == "tethered" else "No WiFi"

    # WiFi icon — 3 arcs
    ix, iy = x + pad + 8, y + h // 2 + 4
    for i in range(3):
        r = 6 + i * 5
        c = color if wifi_ok else t["border"]
        pygame.draw.arc(s, c, (ix - r, iy - r, r * 2, r * 2), 0.4, 2.7, 2)
    pygame.draw.circle(s, color, (ix, iy), 2)

    # Text
    nt = hud.font_sm.render(label, True, t["text_bright"] if wifi_ok else t["text_dim"])
    s.blit(nt, (x + pad + 26, y + h // 2 - 12))
    if ip and wifi_ok:
        it = hud.font_xs.render(ip, True, t["text_dim"])
        s.blit(it, (x + pad + 26, y + h // 2 + 6))

    # ── Divider ──
    pygame.draw.line(s, t["border_lite"], (x + mid, y + 6), (x + mid, y + h - 6))

    # ── Right: Bluetooth ──
    rx = x + mid + pad
    bt_ok = _bt_cache["connected"]
    bt_color = t["primary"] if bt_ok else t["text_dim"]

    # BT icon — simple "B" shape
    bx, by = rx + 6, y + h // 2
    pygame.draw.lines(s, bt_color, False, [
        (bx - 3, by - 6), (bx + 4, by - 1), (bx - 3, by + 4),
        (bx + 4, by + 9), (bx - 3, by + 14)
    ], 2)
    pygame.draw.line(s, bt_color, (bx, by - 8), (bx, by + 16), 2)

    if bt_ok:
        bt_name = _bt_cache["name"][:12]
        bt = hud.font_sm.render(bt_name, True, t["text_bright"])
        s.blit(bt, (rx + 20, y + h // 2 - 12))
        st = hud.font_xs.render("Connected", True, t["text_dim"])
        s.blit(st, (rx + 20, y + h // 2 + 6))
    else:
        bt = hud.font_sm.render("No Device", True, t["text_dim"])
        s.blit(bt, (rx + 20, y + h // 2 - 4))

    return True
