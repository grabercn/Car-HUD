"""System page — time header, smooth-scrolling widget carousel."""

import time
import datetime
import pygame
import widgets

GREEN = (0, 180, 85)
AMBER = (220, 160, 0)
RED = (220, 45, 45)

# Scroll state
_scroll_y = 0.0
_scroll_from = 0.0
_scroll_to = 0.0
_scroll_start_t = 0      # time animation started
_SCROLL_DURATION = 0.35  # seconds for complete scroll
_view_start = 0
_current_pair = 0
_scrolling = False


def draw(hud, stats, music):
    global _scroll_y, _scroll_from, _scroll_to, _scroll_start_t, _view_start, _current_pair, _scrolling

    W, H = hud.width, hud.height
    s = hud.surf
    t = hud.t
    now = datetime.datetime.now()

    # ── Header ──
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
            th = min(80, avail_h - 10)
            logo = hud.honda_logo
            sc = th / logo.get_height()
            logo = pygame.transform.smoothscale(logo, (int(logo.get_width() * sc), th))
            s.blit(logo, ((W - logo.get_width()) // 2, wy + (avail_h - th) // 2))
        return

    n = len(active)
    widget_h = avail_h // 2 - 2
    page_h = avail_h  # one "page" = 2 widgets stacked

    # Determine how long to pause on current view
    # Use the longest view_time of the visible widgets
    if n > 0:
        idx1 = (_current_pair * 2) % n
        idx2 = (_current_pair * 2 + 1) % n
        vt1 = getattr(active[idx1][1], "view_time", 6)
        vt2 = getattr(active[idx2][1], "view_time", 6) if n > 1 else 0
        pause_time = max(vt1, vt2)
    else:
        pause_time = 6

    now_t = time.time()

    # State machine: pause → scroll → pause → scroll...
    if not _scrolling:
        if _view_start == 0:
            _view_start = now_t
        if now_t - _view_start > pause_time and n > 2:
            _scrolling = True
            _current_pair += 1
            _scroll_from = _scroll_y
            _scroll_to = _current_pair * page_h
            _scroll_start_t = now_t
    else:
        # Time-based ease-out (cubic) — fixed duration, pixel-perfect
        elapsed = now_t - _scroll_start_t
        progress = min(elapsed / _SCROLL_DURATION, 1.0)
        # Cubic ease-out: 1 - (1-t)^3
        eased = 1.0 - (1.0 - progress) ** 3
        _scroll_y = _scroll_from + (_scroll_to - _scroll_from) * eased

        if progress >= 1.0:
            _scroll_y = _scroll_to
            _scrolling = False
            _view_start = now_t
            total_pages = (n + 1) // 2
            if _current_pair >= total_pages:
                _current_pair = 0
                _scroll_y = 0.0

    # Clip and render
    clip = pygame.Rect(6, wy, W - 12, avail_h)
    old_clip = s.get_clip()
    s.set_clip(clip)

    offset = int(_scroll_y)
    for i in range(n + 2):
        idx = i % n
        wname, mod = active[idx]
        row = i // 2
        col = i % 2
        slot_y = wy + row * page_h + col * (widget_h + 4) - offset

        if slot_y + widget_h < wy or slot_y > strip_y:
            continue

        try:
            mod.draw(hud, 6, slot_y, W - 12, widget_h, music)
        except Exception:
            pass

    s.set_clip(old_clip)
