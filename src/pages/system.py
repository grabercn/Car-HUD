"""System page — time header, smooth widget carousel."""

import time
import datetime
import pygame
import widgets

GREEN = (0, 180, 85)
AMBER = (220, 160, 0)
RED = (220, 45, 45)

_view_idx = 0        # which pair is currently showing (0-based)
_view_start = 0      # when this pair started showing
_anim_t = 0.0        # 0.0 = resting, >0 = animating (0→1 over ANIM_SECS)
_anim_start = 0
_ANIM_SECS = 0.6


def draw(hud, stats, music):
    global _view_idx, _view_start, _anim_t, _anim_start

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
    n_pairs = max(1, (n + 1) // 2)

    # Get pause time from longest widget in current pair
    i0 = (_view_idx * 2) % n
    pause = getattr(active[i0][1], "view_time", 6)

    # Trigger animation when pause expires
    if _anim_t == 0.0:
        if _view_start == 0:
            _view_start = now_t
        if now_t - _view_start > pause and n_pairs > 1:
            _anim_t = 0.001  # start
            _anim_start = now_t

    # Advance animation
    if _anim_t > 0:
        _anim_t = min((now_t - _anim_start) / _ANIM_SECS, 1.0)
        if _anim_t >= 1.0:
            _view_idx = (_view_idx + 1) % n_pairs
            _anim_t = 0.0
            _view_start = now_t

    # Ease-out curve
    ease = 1.0 - (1.0 - _anim_t) ** 3 if _anim_t > 0 else 0.0
    scroll_px = int(ease * avail_h)

    # Clip to widget area
    clip = pygame.Rect(6, wy, W - 12, avail_h)
    old_clip = s.get_clip()
    s.set_clip(clip)

    # Draw current pair (scrolling up/out)
    for j in range(2):
        wi = (_view_idx * 2 + j) % n
        wname, mod = active[wi]
        draw_y = wy + j * (widget_h + 4) - scroll_px
        if draw_y + widget_h >= wy and draw_y < strip_y:
            try:
                mod.draw(hud, 6, draw_y, W - 12, widget_h, music)
            except Exception:
                pass

    # Draw next pair (scrolling in from below) — only during animation
    if _anim_t > 0:
        next_idx = (_view_idx + 1) % n_pairs
        for j in range(2):
            wi = (next_idx * 2 + j) % n
            wname, mod = active[wi]
            draw_y = wy + avail_h + j * (widget_h + 4) - scroll_px
            if draw_y + widget_h >= wy and draw_y < strip_y:
                try:
                    mod.draw(hud, 6, draw_y, W - 12, widget_h, music)
                except Exception:
                    pass

    s.set_clip(old_clip)
