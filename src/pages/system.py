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

    # Time — massive and centered (Apple style)
    time_str = now.strftime("%I:%M")
    ampm = now.strftime("%p")

    # Use XXL font for time
    tx_full_w = hud.font_xxl.size(time_str)[0] + hud.font_md.size(ampm)[0] + 6
    tx = (W - tx_full_w) // 2
    hud.draw_glow_text(time_str, hud.font_xxl, t["text_bright"], (tx, 8))
    hud.draw_glow_text(ampm, hud.font_md, t["accent"],
                       (tx + hud.font_xxl.size(time_str)[0] + 6, 40))

    date_str = now.strftime("%A, %B %d").upper()
    hud.draw_glow_text(date_str, hud.font_sm, t["text_med"],
                       ((W - hud.font_sm.size(date_str)[0]) // 2, 75))

    # System bars — compact single line with inline values
    ry = 92
    bw = W - 20
    temp = stats.get("cpu_temp", 0)
    tc = t["primary"] if temp < 60 else AMBER if temp < 75 else RED
    mp = stats.get("mem_used_pct", 0)
    mc = t["primary"] if mp < 70 else AMBER if mp < 85 else RED

    # Compact side-by-side bars with wide gap
    half = bw // 2 - 15
    hud.draw_hbar(10, ry, half, 4, temp / 85, tc, "CPU", f"{temp:.0f}°")
    hud.draw_hbar(W // 2 + 5, ry, half, 4, mp / 100, mc, "MEM", f"{mp}%")

    # Widget area
    wy = ry + 20
    pygame.draw.line(s, t["border_lite"], (10, wy), (W - 10, wy))
    
    # Status strip is now floating at bottom right, so we can use almost all height
    strip_y = H - 32

    # Get active widgets and stack them
    active = widgets.get_active(hud, music)
    shown = 0
    avail_h = strip_y - wy - 4
    
    if active:
        # Give more height if only 1 widget, or split it if 2
        widget_h = avail_h if len(active) == 1 else (avail_h // 2 - 4)
        
        for wname, mod in active:
            if shown >= 2:
                break
            widget_y = wy + 4 + shown * (widget_h + 8)
            if widget_y + widget_h > H:
                break
            try:
                result = mod.draw(hud, 10, widget_y, W - 20, widget_h, music)
                if result:
                    shown += 1
            except Exception:
                pass

    # If no widgets, show logo
    if shown == 0:
        if hud.honda_logo:
            target_h = min(80, avail_h - 20)
            logo = hud.honda_logo
            scale = target_h / logo.get_height()
            logo = pygame.transform.smoothscale(
                logo, (int(logo.get_width() * scale), target_h))
            lx = (W - logo.get_width()) // 2
            logo_y = wy + (avail_h - target_h) // 2
            s.blit(logo, (lx, logo_y))
        else:
            ht = hud.font_lg.render("Car-HUD", True, t["primary_dim"])
            s.blit(ht, ((W - ht.get_width()) // 2, wy + avail_h // 2 - 20))
