"""Connectivity widget — WiFi + Bluetooth in one."""

import json
import time
import subprocess
import pygame

name = "Connectivity"
priority = 15

_bt_cache = {"connected": False, "name": "", "last_check": 0}


def is_active(hud, music):
    # Active if WiFi connected OR BT connected
    wifi = False
    try:
        with open("/tmp/car-hud-wifi-data") as f:
            wd = json.load(f)
        wifi = wd.get("state") in ("connected", "tethered")
    except Exception:
        pass

    bt = _check_bt()
    return wifi or bt


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

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=8)
    pygame.draw.rect(s, t["border_lite"], (x, y, w, h), 1, border_radius=8)

    mid = w // 2
    cy_mid = y + h // 2

    # Left half: WiFi
    try:
        with open("/tmp/car-hud-wifi-data") as f:
            wd = json.load(f)
        state = wd.get("state", "")
        ssid = wd.get("ssid", "")
        ip = wd.get("ip", "")

        if state in ("connected", "tethered"):
            color = t["primary"]
            label = ssid if state == "connected" else "Tethered"
        else:
            color = t["text_dim"]
            label = "No WiFi"

        # Signal bars
        bx = x + 12
        by = cy_mid + 6
        for i in range(4):
            bh = 4 + i * 3
            pygame.draw.rect(s, color, (bx + i * 6, by - bh, 4, bh), border_radius=1)

        # SSID
        nt = hud.font_sm.render(label, True, t["text_bright"])
        s.blit(nt, (x + 40, cy_mid - 12))

        # IP below
        if ip:
            it = hud.font_xs.render(ip, True, t["text_dim"])
            s.blit(it, (x + 40, cy_mid + 4))
    except Exception:
        nt = hud.font_sm.render("No WiFi", True, t["text_dim"])
        s.blit(nt, (x + 40, cy_mid - 6))

    # Divider
    pygame.draw.line(s, t["border_lite"], (x + mid, y + 6), (x + mid, y + h - 6))

    # Right half: Bluetooth
    rx = x + mid + 12
    if _bt_cache["connected"]:
        # BT icon
        pygame.draw.circle(s, t["primary"], (rx + 6, cy_mid), 4)
        pygame.draw.circle(s, t["bg"], (rx + 6, cy_mid), 2)

        bt_name = _bt_cache["name"][:12]
        bt = hud.font_sm.render(bt_name, True, t["text_bright"])
        s.blit(bt, (rx + 16, cy_mid - 12))

        st = hud.font_xs.render("Connected", True, t["text_dim"])
        s.blit(st, (rx + 16, cy_mid + 4))
    else:
        pygame.draw.circle(s, t["text_dim"], (rx + 6, cy_mid), 4, 1)
        bt = hud.font_sm.render("No Device", True, t["text_dim"])
        s.blit(bt, (rx + 16, cy_mid - 6))

    return True
