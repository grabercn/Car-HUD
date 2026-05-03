"""System page -- time header with continuous-scroll widget carousel.

Shows clock, date, CPU temp, and memory in a non-overlapping header,
then fills the remaining space (above the H-22 status strip) with
active widgets.  When 3+ widgets are active they scroll continuously;
1-2 widgets are displayed statically.
"""

import time
import datetime
import pygame
import widgets

_PAUSE = 6        # seconds to hold each pair
_SCROLL_PX = 6    # pixels per frame (~90 px/s at 15 fps)


def _draw_pin_icon(s, t, x, y):
    """Draw a small pin icon at (*x*, *y*) using the theme's primary colour."""
    pygame.draw.circle(s, t["primary"], (x, y + 3), 4)       # head
    pygame.draw.line(s, t["primary"], (x, y + 7), (x, y + 14), 2)  # shaft
    pygame.draw.circle(s, t["primary"], (x, y + 14), 1)      # point


def draw(hud, stats, music):
    """Render the System page: header (time/date/CPU/MEM) and widget carousel.

    *stats* is a dict with at least ``cpu_temp`` and ``mem_used_pct``.
    *music* is the shared music-state dict forwarded to widgets.
    """
    W, H = hud.width, hud.height
    s = hud.surf
    t = hud.t
    now = datetime.datetime.now()
    now_t = time.time()

    # ── Header (left: time+ampm, right: date over cpu/mem) ──
    time_str = now.strftime("%I:%M")
    ampm = now.strftime("%p")
    tw = hud.font_xxl.size(time_str)[0]
    ampm_x = 10 + tw + 4
    left_edge = ampm_x + hud.font_sm.size(ampm)[0] + 8  # right end of left block

    date_str = now.strftime("%a, %b %d").upper()
    date_w = hud.font_sm.size(date_str)[0]

    temp = stats.get("cpu_temp", 0)
    mp = stats.get("mem_used_pct", 0)
    sys_str = f"CPU {temp:.0f}\u00b0  MEM {mp}%"
    sys_w = hud.font_xs.size(sys_str)[0]

    # Right-column X: flush right, but never overlapping the left block
    right_x = max(left_edge, W - max(date_w, sys_w) - 10)

    hud.draw_glow_text(time_str, hud.font_xxl, t["text_bright"], (10, 2))
    hud.draw_glow_text(ampm, hud.font_sm, t["accent"], (ampm_x, 32))
    hud.draw_glow_text(date_str, hud.font_sm, t["text_med"], (right_x, 8))
    vt = hud.font_xs.render(sys_str, True, t["text_dim"])
    s.blit(vt, (right_x, 28))

    dy = 50
    pygame.draw.line(s, t["border_lite"], (10, dy), (W - 10, dy))

    # ── Widget area (between divider and status strip) ──
    wy = dy + 3                     # first widget top
    strip_y = H - 22               # status-strip top -- widgets must stay above
    avail_h = strip_y - wy - 2     # total drawable height
    gap = 4                         # vertical gap between widgets
    wh = (avail_h - gap) // 2      # height of each widget slot (for 2-up view)

    active = widgets.get_active(hud, music)
    if not active:
        if hud.honda_logo:
            th = min(80, avail_h - 10)
            logo = hud.honda_logo
            sc = th / logo.get_height()
            logo = pygame.transform.smoothscale(
                logo, (int(logo.get_width() * sc), th))
            s.blit(logo, ((W - logo.get_width()) // 2,
                          wy + (avail_h - th) // 2))
        return

    n = len(active)

    # Static display when only 1 or 2 widgets -- no scrolling needed
    if n <= 2:
        if n == 1:
            active[0][1].draw(hud, 6, wy, W - 12, avail_h, music)
        else:
            for j in range(2):
                active[j][1].draw(hud, 6, wy + j * (wh + gap),
                                  W - 12, wh, music)
        return

    # ── Continuous scroll for 3+ widgets ──
    step = wh + gap  # one widget-slot height including gap

    if not hasattr(draw, '_offset'):
        draw._offset = 0.0
        draw._target = 0
        draw._pause_end = now_t + _PAUSE
        draw._last_top = ""
        draw._last_n = n

    # If widget count changed mid-scroll, reset to avoid jumps
    if n != draw._last_n:
        draw._offset = 0.0
        draw._target = 0
        draw._pause_end = now_t + _PAUSE
        draw._last_n = n

    # Interrupt: priority order changed (new song, phone connected, etc.)
    # -- reset scroll to show the new top widget immediately
    top_name = active[0][0] if active else ""
    if top_name != draw._last_top:
        draw._last_top = top_name
        draw._offset = 0.0
        draw._target = 0
        draw._pause_end = now_t + getattr(active[0][1], "view_time", _PAUSE)

    # Which two widgets are currently visible? Use the longer view_time.
    top_slot = int(draw._offset / step) if step > 0 else 0
    top_wi = top_slot % n
    bot_wi = (top_slot + 1) % n
    pause = max(
        getattr(active[top_wi][1], "view_time", _PAUSE),
        getattr(active[bot_wi][1], "view_time", _PAUSE),
    )

    # Phase: pausing or scrolling
    if draw._offset >= draw._target:
        if now_t >= draw._pause_end:
            draw._target += step
    else:
        draw._offset = min(draw._offset + _SCROLL_PX, draw._target)
        if draw._offset >= draw._target:
            draw._pause_end = now_t + pause

    # Clip to widget area so nothing bleeds into header or status strip
    clip = pygame.Rect(6, wy, W - 12, avail_h)
    old_clip = s.get_clip()
    s.set_clip(clip)

    # Draw visible widgets from the virtual list (doubled for wrap-around)
    pinned = widgets.get_pinned() or []
    offset = int(draw._offset)
    for i in range(n * 2):
        wi = i % n
        slot_y = wy + i * step - offset
        if slot_y > strip_y:
            break
        if slot_y + wh < wy:
            continue
        try:
            active[wi][1].draw(hud, 6, slot_y, W - 12, wh, music)
            if active[wi][0].lower() in pinned:
                _draw_pin_icon(s, t, W - 20, slot_y + 4)
        except Exception:
            pass

    s.set_clip(old_clip)

    # Reset when we've scrolled through all widgets (full cycle)
    if draw._offset >= n * step:
        draw._offset = 0.0
        draw._target = 0
        draw._pause_end = now_t + _PAUSE
