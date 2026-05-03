"""System page — time header, continuous scroll widget carousel."""

import time
import datetime
import pygame
import widgets

_PAUSE = 6        # seconds to hold each pair


def _draw_pin_icon(s, t, x, y):
    """Draw a small pin icon at (x, y)."""
    # Pin head (circle)
    pygame.draw.circle(s, t["primary"], (x, y + 3), 4)
    # Pin shaft
    pygame.draw.line(s, t["primary"], (x, y + 7), (x, y + 14), 2)
    # Pin point
    pygame.draw.circle(s, t["primary"], (x, y + 14), 1)
_SCROLL_PX = 6    # pixels per frame (~90px/sec at 15fps)


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
    wh = avail_h // 2 - 2  # each widget height

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
    if n <= 2:
        for j in range(n):
            h_each = avail_h if n == 1 else wh
            active[j][1].draw(hud, 6, wy + j * (wh + 4), W - 12, h_each, music)
        return

    # ── Continuous scroll for 3+ widgets ──
    if not hasattr(draw, '_offset'):
        draw._offset = 0.0
        draw._target = 0
        draw._pause_end = time.time() + _PAUSE
        draw._last_top = ""

    # Interrupt: if priority order changed (new song, phone connected, etc)
    # reset scroll to show the new top widget immediately
    top_name = active[0][0] if active else ""
    if top_name != draw._last_top:
        draw._last_top = top_name
        draw._offset = 0.0
        draw._target = 0
        draw._pause_end = now_t + getattr(active[0][1], "view_time", 6)

    step = wh + 4  # one widget slot height

    # Which widgets are currently visible? Use their view_time for pause
    top_slot = int(draw._offset / step) if step > 0 else 0
    top_wi = top_slot % n
    bot_wi = (top_slot + 1) % n
    pause = max(
        getattr(active[top_wi][1], "view_time", 6),
        getattr(active[bot_wi][1], "view_time", 6)
    )

    # Phase: pausing or scrolling?
    if draw._offset >= draw._target:
        # Paused — check if pause elapsed
        if now_t >= draw._pause_end:
            draw._target += step
    else:
        # Scrolling — advance by fixed pixels per frame
        draw._offset = min(draw._offset + _SCROLL_PX, draw._target)
        if draw._offset >= draw._target:
            # Arrived — start pause with current widgets' view_time
            draw._pause_end = now_t + pause

    # Clip to widget area
    clip = pygame.Rect(6, wy, W - 12, avail_h)
    old_clip = s.get_clip()
    s.set_clip(clip)

    # Draw all widgets in a virtual list, offset by scroll
    offset = int(draw._offset)
    for i in range(n * 2):  # double for wraparound
        wi = i % n
        slot_y = wy + i * step - offset
        if slot_y > strip_y:
            break
        if slot_y + wh < wy:
            continue
        try:
            active[wi][1].draw(hud, 6, slot_y, W - 12, wh, music)
            # Pin icon in top-right corner if pinned
            wname = active[wi][0].lower()
            if wname in (widgets.get_pinned() or []):
                _draw_pin_icon(s, t, W - 20, slot_y + 4)
        except Exception:
            pass

    s.set_clip(old_clip)

    # Reset when we've scrolled through all widgets
    if draw._offset >= n * step:
        draw._offset = 0.0
        draw._target = 0
        draw._pause_end = now_t + _PAUSE
