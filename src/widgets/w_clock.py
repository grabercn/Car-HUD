"""System Info widget — uptime, temps, storage (not redundant with header clock)."""

import os
import time
import datetime
import pygame

name = "System"
priority = 99  # lowest — fallback


def is_active(hud, music):
    return True


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    # Uptime
    try:
        with open("/proc/uptime") as f:
            up_sec = int(float(f.read().split()[0]))
        up_h, up_m = up_sec // 3600, (up_sec % 3600) // 60
        up_str = f"Up {up_h}h {up_m}m" if up_h > 0 else f"Up {up_m}m"
    except Exception:
        up_str = ""

    # Disk usage
    try:
        st = os.statvfs("/")
        used_gb = (st.f_blocks - st.f_bfree) * st.f_frsize / (1024**3)
        total_gb = st.f_blocks * st.f_frsize / (1024**3)
        disk_str = f"Disk {used_gb:.1f}/{total_gb:.1f}G"
    except Exception:
        disk_str = ""

    # Layout: left column + right column
    cy = y + h // 2

    if up_str:
        ut = hud.font_sm.render(up_str, True, t["text_bright"])
        s.blit(ut, (x + 10, cy - 10))

    if disk_str:
        dt = hud.font_xs.render(disk_str, True, t["text_dim"])
        s.blit(dt, (x + 10, cy + 8))

    # Version on right
    ver = ""
    try:
        with open("/home/chrismslist/car-hud/.version") as f:
            ver = f.read().strip()[:8]
    except Exception:
        pass
    if ver:
        vt = hud.font_xs.render(f"v{ver}", True, t["text_dim"])
        s.blit(vt, (x + w - vt.get_width() - 10, cy - 2))

    return True
