"""System page — time header, auto-rotating widget stack."""

import time
import datetime
import pygame
import widgets

GREEN = (0, 180, 85)
AMBER = (220, 160, 0)
RED = (220, 45, 45)

_rotate_time = 0
_rotate_offset = 0
_fade_frame = 0  # 0=no fade, >0 fading in
_FADE_FRAMES = 15


def draw(hud, stats, music):
    global _rotate_time, _rotate_offset, _fade_frame

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

    # ── Widget area: priority-based auto-rotating stack ──
    wy = dy + 3
    strip_y = H - 22
    avail_h = strip_y - wy - 2

    active = widgets.get_active(hud, music)
    if not active:
        # No widgets — show logo
        if hud.honda_logo:
            target_h = min(80, avail_h - 10)
            logo = hud.honda_logo
            scale = target_h / logo.get_height()
            logo = pygame.transform.smoothscale(
                logo, (int(logo.get_width() * scale), target_h))
            s.blit(logo, ((W - logo.get_width()) // 2, wy + (avail_h - target_h) // 2))
        return

    # Auto-rotate: shift visible window every 8 seconds, with fade
    now_t = time.time()
    if now_t - _rotate_time > 8:
        _rotate_time = now_t
        _rotate_offset += 1
        _fade_frame = _FADE_FRAMES  # trigger fade-in

    if _fade_frame > 0:
        _fade_frame -= 1

    # Show up to 2 widgets from the rotating window
    max_show = min(2, len(active))
    widget_h = (avail_h - (max_show - 1) * 3) // max_show

    # Render widgets to a temp surface for fade effect
    widget_surf = pygame.Surface((W - 12, avail_h), pygame.SRCALPHA)
    shown = 0

    for j in range(max_show):
        idx = (_rotate_offset + j) % len(active)
        wname, mod = active[idx]
        widget_y = j * (widget_h + 3)
        try:
            # Temporarily redirect drawing to widget surface
            old_surf = hud.surf
            hud.surf = widget_surf
            if mod.draw(hud, 0, widget_y, W - 12, widget_h, music):
                shown += 1
            hud.surf = old_surf
        except Exception:
            hud.surf = old_surf

    # Apply smooth ease-in fade
    if _fade_frame > 0:
        t_pct = 1 - _fade_frame / _FADE_FRAMES  # 0→1
        eased = t_pct * t_pct * (3 - 2 * t_pct)  # smoothstep
        widget_surf.set_alpha(int(255 * eased))

    s.blit(widget_surf, (6, wy))
