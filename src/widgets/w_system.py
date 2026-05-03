"""System Info widget -- uptime, disk usage, and version.

Always active.  Shows system uptime on the left and a disk usage bar on
the right.  Uses GREEN/AMBER/RED color constants for disk-usage thresholds.
"""

import os
import pygame

try:
    from config import GREEN, AMBER, RED
except ImportError:
    GREEN = (0, 180, 85)
    AMBER = (220, 160, 0)
    RED = (220, 45, 45)

name = "System"
priority = 99
view_time = 4     # quick glance -- doesn't change fast
show_every = 120  # only show once every 2 minutes


def is_active(hud, music):
    """Always active -- system info is always available."""
    return True


def urgency(hud, music):
    """Low urgency informational widget."""
    return 0


def draw(hud, x, y, w, h, music):
    """Render uptime and disk usage bar."""
    s = hud.surf
    t = hud.t

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    compact = h < 65
    cy = y + h // 2

    # Uptime
    try:
        with open("/proc/uptime") as f:
            up_sec = int(float(f.read().split()[0]))
        up_h, up_m = up_sec // 3600, (up_sec % 3600) // 60
        up_str = f"{up_h}h {up_m}m" if up_h > 0 else f"{up_m}m"
    except Exception:
        up_str = "?"

    # Disk
    try:
        st = os.statvfs("/")
        used = (st.f_blocks - st.f_bfree) * st.f_frsize / (1024**3)
        total = st.f_blocks * st.f_frsize / (1024**3)
        disk_pct = used / total if total > 0 else 0
    except Exception:
        used, total, disk_pct = 0, 0, 0

    # Uptime -- bold, left side
    up_font = hud.font_sm if compact else hud.font_md
    ut = up_font.render(f"Up {up_str}", True, t["text_bright"])
    s.blit(ut, (x + 12, cy - ut.get_height() // 2))

    # Disk -- right side with bar
    bar_x = x + w // 2 + 10
    bar_w = max(1, w // 2 - 30)
    bar_y = cy - 3

    pygame.draw.rect(s, t["border"], (bar_x, bar_y, bar_w, 6), border_radius=3)
    fw = int(bar_w * min(disk_pct, 1))
    dc = GREEN if disk_pct < 0.7 else AMBER if disk_pct < 0.9 else RED
    if fw > 0:
        pygame.draw.rect(s, dc, (bar_x, bar_y, fw, 6), border_radius=3)

    disk_font = hud.font_xs if compact else hud.font_sm
    dt = disk_font.render(f"{used:.0f}/{total:.0f}G", True, t["text_med"])
    s.blit(dt, (bar_x, bar_y + 10))

    return True
