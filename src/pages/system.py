"""System page — clock, system vitals, widget area."""

import datetime
import pygame
import widgets

GREEN = (0, 180, 85)
AMBER = (220, 160, 0)
RED = (220, 45, 45)


def draw(hud, stats, music):
    W, H = hud.width, hud.height
    s = hud.surf
    t = hud.t
    now = datetime.datetime.now()

    # ── Top: Time + Date ──
    time_str = now.strftime("%I:%M")
    ampm = now.strftime("%p")

    # Time left-aligned, date right-aligned — single line, no overlap
    hud.draw_glow_text(time_str, hud.font_xxl, t["text_bright"], (10, 2))
    ampm_x = 10 + hud.font_xxl.size(time_str)[0] + 4
    hud.draw_glow_text(ampm, hud.font_sm, t["accent"], (ampm_x, 32))

    date_str = now.strftime("%a, %b %d").upper()
    dw = hud.font_sm.size(date_str)[0]
    hud.draw_glow_text(date_str, hud.font_sm, t["text_med"], (W - dw - 10, 8))

    # CPU + MEM inline with date
    temp = stats.get("cpu_temp", 0)
    mp = stats.get("mem_used_pct", 0)
    tc = t["primary"] if temp < 60 else AMBER if temp < 75 else RED
    mc = t["primary"] if mp < 70 else AMBER if mp < 85 else RED

    vitals = f"CPU {temp:.0f}°  MEM {mp}%"
    vt = hud.font_xs.render(vitals, True, t["text_dim"])
    s.blit(vt, (W - vt.get_width() - 10, 28))

    # Thin divider
    dy = 52
    pygame.draw.line(s, t["border_lite"], (10, dy), (W - 10, dy))

    # ── Widget area: fill remaining space ──
    wy = dy + 4
    strip_y = H - 22  # status strip starts here

    active = widgets.get_active(hud, music)
    shown = 0
    avail_h = strip_y - wy - 4

    if active:
        # Dynamic: 1 widget gets all space, 2 widgets split, max 3
        max_widgets = min(3, len(active))
        widget_h = (avail_h - (max_widgets - 1) * 4) // max_widgets

        for wname, mod in active:
            if shown >= max_widgets:
                break
            widget_y = wy + shown * (widget_h + 4)
            try:
                result = mod.draw(hud, 6, widget_y, W - 12, widget_h, music)
                if result:
                    shown += 1
            except Exception:
                pass

    # No widgets — show logo
    if shown == 0:
        if hud.honda_logo:
            target_h = min(80, avail_h - 10)
            logo = hud.honda_logo
            scale = target_h / logo.get_height()
            logo = pygame.transform.smoothscale(
                logo, (int(logo.get_width() * scale), target_h))
            s.blit(logo, ((W - logo.get_width()) // 2, wy + (avail_h - target_h) // 2))
        else:
            ht = hud.font_lg.render("Car-HUD", True, t["primary_dim"])
            s.blit(ht, ((W - ht.get_width()) // 2, wy + avail_h // 2 - 20))
