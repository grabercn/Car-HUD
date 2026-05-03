"""Connectivity widget -- WiFi + Bluetooth unified.

Shows WiFi network name/IP on the left and paired Bluetooth device on the
right, separated by a vertical divider.  Uses cached Bluetooth state to
avoid running bluetoothctl every frame.
"""

import json
import time
import subprocess
import pygame

try:
    from config import WIFI_DATA, GREEN, AMBER, RED
except ImportError:
    WIFI_DATA = "/tmp/car-hud-wifi-data"
    GREEN = (0, 180, 85)
    AMBER = (220, 160, 0)
    RED = (220, 45, 45)

name = "Connectivity"
priority = 15
view_time = 5
show_every = 60  # show once a minute unless phone connects

_bt_cache = {"connected": False, "name": "", "last_check": 0}


def is_active(hud, music):
    """Return True when WiFi is connected/tethered or a BT phone is paired."""
    wifi = False
    try:
        with open(WIFI_DATA) as f:
            wd = json.load(f)
        wifi = wd.get("state") in ("connected", "tethered")
    except Exception:
        pass
    try:
        return wifi or _check_bt()
    except Exception:
        return wifi


def _check_bt():
    """Check for a connected Bluetooth phone (cached for 5 seconds).

    Skips OBD adapter names so only actual phones are reported.
    """
    now = time.time()
    if now - _bt_cache["last_check"] < 5:
        return _bt_cache["connected"]
    _bt_cache["last_check"] = now
    _bt_cache["connected"] = False
    try:
        # Check all connected devices, find a phone (not OBD adapter)
        r = subprocess.run(["bluetoothctl", "devices", "Connected"],
                           capture_output=True, text=True, timeout=3)
        for line in r.stdout.splitlines():
            parts = line.split(" ", 2)
            if len(parts) < 3:
                continue
            mac = parts[1]
            dev_name = parts[2] if len(parts) > 2 else ""
            # Skip OBD adapters
            if any(x in dev_name.lower() for x in ["vlink", "obd", "elm", "icar", "vgate"]):
                continue
            # Check if it's a phone
            info = subprocess.run(["bluetoothctl", "info", mac],
                                  capture_output=True, text=True, timeout=2)
            if "Icon: phone" in info.stdout:
                _bt_cache["connected"] = True
                _bt_cache["name"] = dev_name
                break
    except Exception:
        pass
    return _bt_cache["connected"]


_boot_time = time.time()

def urgency(hud, music):
    """High priority for first 30 seconds after boot."""
    if time.time() - _boot_time < 30:
        return -50
    return 0


def draw(hud, x, y, w, h, music):
    """Render WiFi status (left) and Bluetooth status (right) with divider."""
    s = hud.surf
    t = hud.t

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    compact = h < 65
    mid = w // 2
    pad = 10

    # ── Left: WiFi ──
    wifi_ok = False
    try:
        with open(WIFI_DATA) as f:
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

    # Text -- use smaller font in compact mode
    label_font = hud.font_xs if compact else hud.font_sm
    nt = label_font.render(label, True, t["text_bright"] if wifi_ok else t["text_dim"])
    s.blit(nt, (x + pad + 26, y + h // 2 - 12))
    if ip and wifi_ok and not compact:
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

    bt_font = hud.font_xs if compact else hud.font_sm
    if bt_ok:
        bt_name = _bt_cache["name"][:12]
        bt = bt_font.render(bt_name, True, t["text_bright"])
        s.blit(bt, (rx + 20, y + h // 2 - 12))
        if not compact:
            st = hud.font_xs.render("Connected", True, GREEN)
            s.blit(st, (rx + 20, y + h // 2 + 6))
    else:
        bt = bt_font.render("No Device", True, t["text_dim"])
        s.blit(bt, (rx + 20, y + h // 2 - 4))

    return True
