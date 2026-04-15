"""Vehicle page — OBD instrument cluster with scrolling widget."""

import math
import time
import datetime
import pygame
import widgets

GREEN = (0, 180, 85)
AMBER = (220, 160, 0)
RED = (220, 45, 45)

_view_idx = 0
_view_start = 0
_anim_t = 0.0
_anim_start = 0
_ANIM_SECS = 0.5


def draw(hud, obd, music):
    global _view_idx, _view_start, _anim_t, _anim_start

    W, H = hud.width, hud.height
    s = hud.surf
    t = hud.t
    vd = hud.smooth_data
    now = datetime.datetime.now()
    now_t = time.time()

    rpm = vd.get("RPM", 0)
    speed = vd.get("SPEED", 0) * 0.621371
    load = vd.get("ENGINE_LOAD", 0)
    throttle = vd.get("THROTTLE_POS", 0)
    fuel = vd.get("FUEL_LEVEL", 0)
    hv = vd.get("HYBRID_BATTERY_REMAINING", 0)
    cool = vd.get("COOLANT_TEMP", 0)
    volts = vd.get("CONTROL_MODULE_VOLTAGE", 0)
    intake = vd.get("INTAKE_TEMP", 0)
    ev = rpm < 100

    # Warnings
    wy_off = 0
    for wt in (obd.get("warnings") or [])[:2]:
        txt = hud.font_sm.render(wt, True, RED)
        pygame.draw.rect(s, (25, 5, 5), (0, wy_off, W, txt.get_height() + 4))
        s.blit(txt, ((W - txt.get_width()) // 2, wy_off + 2))
        wy_off += txt.get_height() + 4

    # ── Gauges ──
    cx, cy = W // 2, 148
    hud.draw_arc_gauge(cx, cy, 115, 14, min(speed / 140, 1.0), t["primary"],
                       start=math.pi * 1.15, end=-math.pi * 0.15, ticks=True)
    rc = t["primary_dim"] if rpm < 3000 else AMBER if rpm < 5500 else RED
    hud.draw_arc_gauge(cx, cy, 97, 4, min(rpm / 7000, 1.0), rc,
                       start=math.pi * 1.15, end=-math.pi * 0.15)

    sp = f"{int(speed)}"
    hud.draw_glow_text(sp, hud.font_xxl, t["text_bright"],
                       (cx - hud.font_xxl.size(sp)[0] // 2, cy - 65))
    hud.draw_glow_text("MPH", hud.font_md, t["text_dim"],
                       (cx - hud.font_md.size("MPH")[0] // 2, cy - 2))

    mc = GREEN if ev else t["primary"]
    pygame.draw.rect(s, mc, (cx - 28, cy + 29, 56, 22), border_radius=4)
    ml = hud.font_sm.render("EV" if ev else "GAS", True, (0, 0, 0))
    s.blit(ml, (cx - ml.get_width() // 2, cy + 33))

    # Left: PWR/CHG
    lx, ly, lr = 65, 148, 70
    if ev:
        hud.draw_arc_gauge(lx, ly, lr, 10, min(throttle / 80, 1.0), GREEN,
                           start=math.pi * 1.3, end=math.pi * 0.7, ticks=True)
    else:
        lp = min(load / 100, 1.0)
        pc = t["primary"] if lp < 0.7 else AMBER if lp < 0.9 else RED
        hud.draw_arc_gauge(lx, ly, lr, 10, lp, pc, start=math.pi, end=math.pi * 0.7, ticks=True)
        cp = 0.3 if (throttle < 5 and rpm > 800) else 0.0
        hud.draw_arc_gauge(lx, ly, lr, 10, cp, GREEN, start=math.pi, end=math.pi * 1.3)
    hud.draw_glow_text("PWR", hud.font_xs, t["text_dim"], (lx - 12, ly - lr - 14))
    hud.draw_glow_text("CHG", hud.font_xs, GREEN, (lx - 12, ly + lr + 4))

    # Right: Fuel/Batt
    rx, ry, rr = W - 65, 148, 70
    fc = GREEN if fuel > 20 else AMBER if fuel > 10 else RED
    hud.draw_arc_gauge(rx, ry, rr, 10, fuel / 100, fc, start=math.pi * 0.3, end=-math.pi * 0.3, ticks=True)
    bc = GREEN if hv > 30 else AMBER if hv > 15 else RED
    hud.draw_arc_gauge(rx, ry, rr - 18, 6, hv / 100, bc, start=math.pi * 0.3, end=-math.pi * 0.3)
    hud.draw_glow_text("FUEL", hud.font_xs, t["text_dim"], (rx - 15, ry - rr - 14))
    hud.draw_glow_text("BATT", hud.font_xs, t["text_dim"], (rx - 15, ry + rr + 4))

    # Top info
    ty = 6 + wy_off
    hud.draw_glow_text(now.strftime("%I:%M"), hud.font_md, t["text_bright"], (12, ty))
    vl = f"{volts:.1f}V"
    hud.draw_glow_text(vl, hud.font_md, t["text_med"], (W - hud.font_md.size(vl)[0] - 12, ty))
    hud.draw_glow_text(f"{intake:.0f}C", hud.font_xs, t["text_dim"], (cx + 60, cy + 60))
    hud.draw_glow_text(f"{cool:.0f}C", hud.font_xs, t["text_med"],
                       (cx - 60 - hud.font_xs.size(f"{cool:.0f}C")[0], cy + 60))

    # ── Widget scroll ──
    wly = cy + 82
    widget_h = H - wly - 24

    active = widgets.get_active(hud, music)
    if not active:
        return

    n = len(active)
    cur_mod = active[_view_idx % n][1]
    pause = getattr(cur_mod, "view_time", 6)

    if _anim_t == 0.0:
        if _view_start == 0:
            _view_start = now_t
        if now_t - _view_start > pause and n > 1:
            _anim_t = 0.001
            _anim_start = now_t

    if _anim_t > 0:
        _anim_t = min((now_t - _anim_start) / _ANIM_SECS, 1.0)
        if _anim_t >= 1.0:
            _view_idx = (_view_idx + 1) % n
            _anim_t = 0.0
            _view_start = now_t

    ease = 1.0 - (1.0 - _anim_t) ** 3 if _anim_t > 0 else 0.0
    scroll_px = int(ease * widget_h)

    clip = pygame.Rect(6, wly, W - 12, widget_h)
    old_clip = s.get_clip()
    s.set_clip(clip)

    # Current widget (scrolling out)
    ci = _view_idx % n
    active[ci][1].draw(hud, 6, wly - scroll_px, W - 12, widget_h, music)

    # Next widget (scrolling in)
    if _anim_t > 0:
        ni = (_view_idx + 1) % n
        active[ni][1].draw(hud, 6, wly + widget_h - scroll_px, W - 12, widget_h, music)

    s.set_clip(old_clip)
