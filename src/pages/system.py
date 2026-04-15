"""System page — time header, continuous-scroll widget carousel."""

import time
import datetime
import pygame
import widgets

GREEN = (0, 180, 85)
AMBER = (220, 160, 0)
RED = (220, 45, 45)

_scroll_offset = 0      # current pixel offset (0 = resting)
_scroll_target = 0      # target offset to scroll to
_scroll_idx = 0         # which pair of widgets we're showing
_last_scroll_time = 0
_SCROLL_INTERVAL = 8    # seconds between scrolls
_SCROLL_SPEED = 8       # pixels per frame during scroll


def draw(hud, stats, music):
    global _scroll_offset, _scroll_target, _scroll_idx, _last_scroll_time

    W, H = hud.width, hud.height
    s = hud.surf
    t = hud.t
    now = datetime.datetime.now()

    # ── Header: Time + vitals ──
    time_str = now.strftime("%I:%M")
    ampm = now.strftime("%p")
    hud.draw_glow_text(time_str, hud.font_xxl, t["text_bright"], (10, 2))
    ampm_x = 10 + hud.font_xxl.size(time_str)[0] + 4
    hud.draw_glow_text(ampm, hud.font_sm, t["accent"], (ampm_x, 32))

    date_str = now.strftime("%a, %b %d").upper()
    dw = hud.font_sm.size(date_str)[0]
    hud.draw_glow_text(date_str, hud.font_sm, t["text_med"], (W - dw - 10, 8))

    temp = stats.get("cpu_temp", 0)
    mp = stats.get("mem_used_pct", 0)
    vt = hud.font_xs.render(f"CPU {temp:.0f}°  MEM {mp}%", True, t["text_dim"])
    s.blit(vt, (W - vt.get_width() - 10, 28))

    dy = 50
    pygame.draw.line(s, t["border_lite"], (10, dy), (W - 10, dy))

    # ── Widget carousel ──
    wy = dy + 3
    strip_y = H - 22
    avail_h = strip_y - wy - 2

    active = widgets.get_active(hud, music)
    if not active:
        if hud.honda_logo:
            target_h = min(80, avail_h - 10)
            logo = hud.honda_logo
            scale = target_h / logo.get_height()
            logo = pygame.transform.smoothscale(
                logo, (int(logo.get_width() * scale), target_h))
            s.blit(logo, ((W - logo.get_width()) // 2, wy + (avail_h - target_h) // 2))
        return

    widget_h = avail_h // 2 - 2  # each widget gets half height
    total_pair_h = avail_h  # height of one "page" of 2 widgets

    # Trigger scroll every SCROLL_INTERVAL seconds
    now_t = time.time()
    if now_t - _last_scroll_time > _SCROLL_INTERVAL and len(active) > 2:
        _last_scroll_time = now_t
        _scroll_idx += 1
        _scroll_target = _scroll_idx * total_pair_h

    # Animate scroll toward target
    if _scroll_offset < _scroll_target:
        _scroll_offset = min(_scroll_offset + _SCROLL_SPEED, _scroll_target)

    # Clip to widget area
    clip = pygame.Rect(6, wy, W - 12, avail_h)
    old_clip = s.get_clip()
    s.set_clip(clip)

    # Render all widgets in a virtual scroll list
    n = len(active)
    for i in range(n + 2):  # extra for wrap-around
        idx = i % n
        wname, mod = active[idx]
        # Each widget at position i in the virtual list
        slot_y = wy + (i // 2) * total_pair_h + (i % 2) * (widget_h + 4) - _scroll_offset

        # Skip if completely off screen
        if slot_y + widget_h < wy or slot_y > strip_y:
            continue

        try:
            mod.draw(hud, 6, slot_y, W - 12, widget_h, music)
        except Exception:
            pass

    s.set_clip(old_clip)

    # Reset scroll when we've gone through all widgets
    if n <= 2:
        _scroll_offset = 0
        _scroll_target = 0
        _scroll_idx = 0
    elif _scroll_offset >= ((n + 1) // 2) * total_pair_h:
        _scroll_offset = 0
        _scroll_target = 0
        _scroll_idx = 0
        _last_scroll_time = now_t
