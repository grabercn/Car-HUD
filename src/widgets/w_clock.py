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

    # Large time
    time_str = now.strftime("%I:%M %p")
    ts = hud.font_lg.render(time_str, True, t["text_bright"])
    s.blit(ts, (x, y))

    # Date on right
    date_str = now.strftime("%b %d")
    dt = hud.font_sm.render(date_str, True, t["text_med"])
    s.blit(dt, (x + w - dt.get_width(), y + 4))

    # Ambient temp if available
    amb = hud.smooth_data.get("AMBIANT_AIR_TEMP")
    if amb:
        at = hud.font_sm.render(f"{amb:.0f}°C", True, t["text_dim"])
        s.blit(at, (x + w - at.get_width(), y + 22))

    return True
