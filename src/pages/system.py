"""System page — clock, system stats, widget stack."""

import datetime
import pygame
import widgets

GREEN = (0, 180, 85)
AMBER = (220, 160, 0)
RED = (220, 45, 45)


def draw(hud, stats, music):
    """Draw the system info page with stacked widgets."""
    W, H = hud.width, hud.height
    s = hud.surf
    t = hud.t
    now = datetime.datetime.now()

    # Time — large and centered
    time_str = now.strftime("%I:%M")
    ampm = now.strftime("%p")

    tx_full_w = hud.font_xl.size(time_str)[0] + hud.font_md.size(ampm)[0] + 6
    tx = (W - tx_full_w) // 2
    hud.draw_glow_text(time_str, hud.font_xl, t["primary"], (tx, 4))
    hud.draw_glow_text(ampm, hud.font_md, t["accent"],
                       (tx + hud.font_xl.size(time_str)[0] + 6, 20))

    date_str = now.strftime("%A, %B %d").upper()
    hud.draw_glow_text(date_str, hud.font_sm, t["text_med"],
                       ((W - hud.font_sm.size(date_str)[0]) // 2, 44))

    dy = 62
    pygame.draw.line(s, t["border_lite"], (10, dy), (W - 10, dy))

    # System bars
    ry = dy + 8
    hw = W // 2 - 20
    pad = 10

    temp = stats.get("cpu_temp", 0)
    tc = t["primary"] if temp < 60 else AMBER if temp < 75 else RED
    hud.draw_hbar(pad, ry + 16, hw, 12, temp / 85, tc, "CPU", f"{temp:.0f}°C")

    mp = stats.get("mem_used_pct", 0)
    mc = t["primary"] if mp < 70 else AMBER if mp < 85 else RED
    hud.draw_hbar(W // 2 + pad, ry + 16, hw, 12, mp / 100, mc, "MEM", f"{mp}%")

    # Widget area — below system bars, above status strip
    wy = ry + 42
    pygame.draw.line(s, t["border_lite"], (10, wy), (W - 10, wy))
    strip_y = H - 26

    # Get active widgets and stack them (up to 2)
    active = widgets.get_active(hud, music)
    shown = 0

    for wname, mod in active:
        if shown >= 2:
            break
        widget_y = wy + 3 + shown * 60
        if widget_y + 55 > strip_y:
            break
        try:
            result = mod.draw(hud, 4, widget_y, W - 8, 55, music)
            if result:
                shown += 1
        except Exception:
            pass

    # If no widgets, show logo
    if shown == 0:
        avail_h = strip_y - wy - 4
        if hud.honda_logo:
            target_h = min(55, avail_h - 4)
            logo = hud.honda_logo
            scale = target_h / logo.get_height()
            logo = pygame.transform.smoothscale(
                logo, (int(logo.get_width() * scale), target_h))
            lx = (W - logo.get_width()) // 2
            logo_y = wy + (avail_h - target_h) // 2 + 2
            s.blit(logo, (lx, logo_y))
        else:
            ht = hud.font_sm.render("Car-HUD", True, t["primary_dim"])
            s.blit(ht, ((W - ht.get_width()) // 2, wy + 20))
