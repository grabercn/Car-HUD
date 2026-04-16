"""Radar Detector widget — Cobra RAD 700i alerts and status."""

import json
import time
import math
import pygame

name = "Radar"
priority = 5  # very high — alerts are critical
view_time = 15

RED = (220, 45, 45)
AMBER = (220, 160, 0)

_last_alert_time = 0


def is_active(hud, music):
    try:
        with open("/tmp/car-hud-cobra-data") as f:
            d = json.load(f)
        return d.get("connected", False) and time.time() - d.get("timestamp", 0) < 30
    except Exception:
        return False


def urgency(hud, music):
    """Jump to front immediately when alert is active."""
    global _last_alert_time
    try:
        with open("/tmp/car-hud-cobra-data") as f:
            d = json.load(f)
        if d.get("alert"):
            _last_alert_time = time.time()
            return -200  # highest urgency — override everything
    except Exception:
        pass
    # Stay prominent for 10s after alert clears
    if time.time() - _last_alert_time < 10:
        return -100
    return 0


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t

    try:
        with open("/tmp/car-hud-cobra-data") as f:
            d = json.load(f)
    except Exception:
        d = {}

    alert = d.get("alert")
    strength = d.get("alert_strength", 0)
    gps_speed = d.get("gps_speed", 0)
    status = d.get("status", "")

    if alert:
        # ── ALERT MODE — full widget, bold, impossible to miss ──
        # Red background pulse
        pulse = (math.sin(time.time() * 6) + 1) / 2  # fast pulse
        bg_r = int(60 + 40 * pulse)
        pygame.draw.rect(s, (bg_r, 5, 5), (x, y, w, h), border_radius=6)
        pygame.draw.rect(s, RED, (x, y, w, h), 2, border_radius=6)

        cy = y + h // 2

        # Band name — huge
        bt = hud.font_xxl.render(alert, True, (255, 255, 255))
        s.blit(bt, (x + 12, cy - bt.get_height() // 2 - 4))

        # Strength bar
        bar_x = x + bt.get_width() + 24
        bar_w = w - bt.get_width() - 40
        bar_h = 10
        bar_y = cy - bar_h // 2

        pygame.draw.rect(s, (80, 10, 10), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        fill = int(bar_w * min(strength / 10, 1))
        if fill > 0:
            # Color gradient: green → yellow → red based on strength
            if strength <= 3:
                bar_c = (0, 180, 85)
            elif strength <= 6:
                bar_c = AMBER
            else:
                bar_c = RED
            pygame.draw.rect(s, bar_c, (bar_x, bar_y, fill, bar_h), border_radius=4)

        # Strength number
        st = hud.font_md.render(f"{strength}/10", True, (255, 200, 200))
        s.blit(st, (x + w - st.get_width() - 10, cy - 8))

    else:
        # ── IDLE MODE — subtle status bar ──
        pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

        cy = y + h // 2

        # Radar icon — antenna/wave
        ix = x + 16
        for i in range(3):
            r = 5 + i * 5
            pygame.draw.arc(s, t["primary"], (ix - r, cy - r, r * 2, r * 2), -0.5, 0.5, 2)
        pygame.draw.circle(s, t["primary"], (ix, cy), 3)

        # Status text
        nt = hud.font_md.render("Cobra RAD 700i", True, t["text_bright"])
        s.blit(nt, (x + 34, cy - 12))

        st = hud.font_xs.render("Monitoring" if status == "active" else status, True, t["text_dim"])
        s.blit(st, (x + 34, cy + 6))

        # GPS speed if available
        if gps_speed > 0:
            gt = hud.font_sm.render(f"{gps_speed} mph", True, t["text_med"])
            s.blit(gt, (x + w - gt.get_width() - 10, cy - 4))

    return True
