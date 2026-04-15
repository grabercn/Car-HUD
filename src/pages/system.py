"""System page — time header, rotating widget stack."""

import time
import datetime
import pygame
import widgets

GREEN = (0, 180, 85)
AMBER = (220, 160, 0)
RED = (220, 45, 45)

_CYCLE_SECS = 8  # seconds per widget pair
_last_idx = -1
_slide_offset = 0


def draw(hud, stats, music):
    W, H = hud.width, hud.height
    s = hud.surf
    t = hud.t
    now = datetime.datetime.now()
    now_t = time.time()

    # ── Header ──
    time_str = now.strftime("%I:%M")
    ampm = now.strftime("%p")
    hud.draw_glow_text(time_str, hud.font_xxl, t["text_bright"], (10, 2))
    hud.draw_glow_text(ampm, hud.font_sm, t["accent"],
                       (10 + hud.font_xxl.size(time_str)[0] + 4, 32))

    date_str = now.strftime("%a, %b %d").upper()
    hud.draw_glow_text(date_str, hud.font_sm, t["text_med"],
                       (W - hud.font_sm.size(date_str)[0] - 10, 8))

    temp = stats.get("cpu_temp", 0)
    mp = stats.get("mem_used_pct", 0)
    vt = hud.font_xs.render(f"CPU {temp:.0f}°  MEM {mp}%", True, t["text_dim"])
    s.blit(vt, (W - vt.get_width() - 10, 28))

    dy = 50
    pygame.draw.line(s, t["border_lite"], (10, dy), (W - 10, dy))

    # ── Widget area ──
    wy = dy + 3
    strip_y = H - 22
    avail_h = strip_y - wy - 2
    widget_h = avail_h // 2 - 2

    active = widgets.get_active(hud, music)
    if not active:
        if hud.honda_logo:
            th = min(80, avail_h - 10)
            logo = hud.honda_logo
            sc = th / logo.get_height()
            logo = pygame.transform.smoothscale(logo, (int(logo.get_width() * sc), th))
            s.blit(logo, ((W - logo.get_width()) // 2, wy + (avail_h - th) // 2))
        return

    n = len(active)

    if n == 1:
        active[0][1].draw(hud, 6, wy, W - 12, avail_h, music)
        return

    # 2+ widgets: show 2 at a time, rotate based on wall clock
    global _last_idx, _slide_offset
    top_idx = int(now_t / _CYCLE_SECS) % n
    bot_idx = (top_idx + 1) % n

    # Trigger slide when index changes
    if top_idx != _last_idx:
        _last_idx = top_idx
        _slide_offset = 20  # start 20px below, slide up

    # Decay slide offset (simple ease)
    if _slide_offset > 0:
        _slide_offset = max(0, _slide_offset - 4)  # ~5 frames at 15fps

    try:
        active[top_idx][1].draw(hud, 6, wy + _slide_offset, W - 12, widget_h, music)
    except Exception:
        pass

    try:
        active[bot_idx][1].draw(hud, 6, wy + widget_h + 4 + _slide_offset, W - 12, widget_h, music)
    except Exception:
        pass
