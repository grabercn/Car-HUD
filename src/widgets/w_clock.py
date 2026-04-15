"""Clock / Temperature widget."""

import datetime
import pygame

name = "Clock"
priority = 99  # lowest — fallback widget


def is_active(hud, music):
    return True  # always available


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t
    now = datetime.datetime.now()

    ts = hud.font_md.render(now.strftime("%I:%M %p"), True, t["text_med"])
    s.blit(ts, (x, y + 2))

    amb = hud.smooth_data.get("AMBIANT_AIR_TEMP")
    if amb:
        at = hud.font_md.render(f"{amb:.0f}°C", True, t["text_dim"])
        s.blit(at, (x + w - at.get_width(), y + 2))

    return True
