"""Clock / Date / Temperature widget."""

import datetime
import pygame

name = "Clock"
priority = 99


def is_active(hud, music):
    return True


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t
    now = datetime.datetime.now()

    # Create a nice minimalist rounded box for the clock
    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=8)
    pygame.draw.rect(s, t["border_lite"], (x, y, w, h), 1, border_radius=8)

    # Large time
    time_str = now.strftime("%I:%M %p")
    ts = hud.font_lg.render(time_str, True, t["text_bright"])
    # Center vertically
    ty = y + (h - ts.get_height()) // 2
    s.blit(ts, (x + 12, ty))

    # Date on right
    date_str = now.strftime("%A, %b %d")
    dt = hud.font_sm.render(date_str, True, t["text_med"])
    s.blit(dt, (x + w - dt.get_width() - 12, ty))

    # Ambient temp if available, below date
    amb = hud.smooth_data.get("AMBIANT_AIR_TEMP")
    if amb:
        at = hud.font_md.render(f"{amb:.0f}°C", True, t["primary"])
        s.blit(at, (x + w - at.get_width() - 12, ty + dt.get_height() + 4))

    return True
