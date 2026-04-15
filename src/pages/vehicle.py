"""Vehicle page — OBD instrument cluster with scrolling widget."""

import math
import time
import datetime
import pygame
import widgets

GREEN = (0, 180, 85)
AMBER = (220, 160, 0)
RED = (220, 45, 45)

_scroll_offset = 0
_scroll_target = 0
_scroll_idx = 0
_last_scroll_time = 0
_SCROLL_INTERVAL = 6
_SCROLL_SPEED = 6


def draw(hud, obd, music):
    global _scroll_offset, _scroll_target, _scroll_idx, _last_scroll_time

    W, H = hud.width, hud.height
    s = hud.surf
    t = hud.t
    vd = hud.smooth_data
    now = datetime.datetime.now()

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
    wy = 0
    all_warnings = (obd.get("warnings") or [])[:]
    for dtc in (obd.get("dtcs") or []):
        all_warnings.append(f"ENGINE CODE: {dtc}")
    for wt in all_warnings[:3]:
        txt = hud.font_sm.render(wt, True, RED)
        pygame.draw.rect(s, (25, 5, 5), (0, wy, W, txt.get_height() + 4))
        s.blit(txt, ((W - txt.get_width()) // 2, wy + 2))
        wy += txt.get_height() + 4

    # ── Central Speedo ──
    cx, cy = W // 2, 148
    r_speed = 115
    sp_pct = min(speed / 140, 1.0)
    hud.draw_arc_gauge(cx, cy, r_speed, 14, sp_pct, t["primary"],
                       start=math.pi * 1.15, end=-math.pi * 0.15, ticks=True)

    rpm_pct = min(rpm / 7000, 1.0)
    rc = t["primary_dim"] if rpm < 3000 else AMBER if rpm < 5500 else RED
    hud.draw_arc_gauge(cx, cy, r_speed - 18, 4, rpm_pct, rc,
                       start=math.pi * 1.15, end=-math.pi * 0.15)

    sp_str = f"{int(speed)}"
    sp_pos = (cx - hud.font_xxl.size(sp_str)[0] // 2, cy - 65)
    hud.draw_glow_text(sp_str, hud.font_xxl, t["text_bright"], sp_pos)

    unit_pos = (cx - hud.font_md.size("MPH")[0] // 2, cy - 2)
    hud.draw_glow_text("MPH", hud.font_md, t["text_dim"], unit_pos)

    # EV/GAS badge
    mc = GREEN if ev else t["primary"]
    badge_w, badge_h = 56, 22
    pygame.draw.rect(s, (0, 0, 0, 100),
                     (cx - badge_w // 2 - 1, cy + 28, badge_w + 2, badge_h + 2), border_radius=4)
    pygame.draw.rect(s, mc, (cx - badge_w // 2, cy + 29, badge_w, badge_h), border_radius=4)
    ml = hud.font_sm.render("EV" if ev else "GAS", True, (0, 0, 0))
    s.blit(ml, (cx - ml.get_width() // 2, cy + 29 + (badge_h - ml.get_height()) // 2))

    # ── Left: CHG/PWR ──
    lx, ly = 65, 148
    lr = 70
    if ev:
        hud.draw_arc_gauge(lx, ly, lr, 10, min(throttle / 80, 1.0), GREEN,
                           start=math.pi * 1.3, end=math.pi * 0.7, ticks=True)
    else:
        load_pct = min(load / 100, 1.0)
        pc = t["primary"] if load_pct < 0.7 else AMBER if load_pct < 0.9 else RED
        hud.draw_arc_gauge(lx, ly, lr, 10, load_pct, pc,
                           start=math.pi, end=math.pi * 0.7, ticks=True)
        chg_pct = 0.3 if (throttle < 5 and rpm > 800) else 0.0
        hud.draw_arc_gauge(lx, ly, lr, 10, chg_pct, GREEN,
                           start=math.pi, end=math.pi * 1.3)

    hud.draw_glow_text("PWR", hud.font_xs, t["text_dim"], (lx - 12, ly - lr - 14))
    hud.draw_glow_text("CHG", hud.font_xs, GREEN, (lx - 12, ly + lr + 4))

    # ── Right: Fuel & Battery ──
    rx, ry = W - 65, 148
    rr = 70
    fc = GREEN if fuel > 20 else AMBER if fuel > 10 else RED
    hud.draw_arc_gauge(rx, ry, rr, 10, fuel / 100, fc,
                       start=math.pi * 0.3, end=-math.pi * 0.3, ticks=True)
    bc = GREEN if hv > 30 else AMBER if hv > 15 else RED
    hud.draw_arc_gauge(rx, ry, rr - 18, 6, hv / 100, bc,
                       start=math.pi * 0.3, end=-math.pi * 0.3)

    hud.draw_glow_text("FUEL", hud.font_xs, t["text_dim"], (rx - 15, ry - rr - 14))
    hud.draw_glow_text("BATT", hud.font_xs, t["text_dim"], (rx - 15, ry + rr + 4))

    # ── Top strip ──
    ty = 6 + wy
    hud.draw_glow_text(now.strftime("%I:%M"), hud.font_md, t["text_bright"], (12, ty))
    vl_str = f"{volts:.1f}V"
    hud.draw_glow_text(vl_str, hud.font_md, t["text_med"],
                       (W - hud.font_md.size(vl_str)[0] - 12, ty))

    # ── Temps ──
    hud.draw_glow_text(f"AIR {intake:.0f}C", hud.font_xs, t["text_dim"],
                       (cx + 60, cy + 60))
    hud.draw_glow_text(f"H2O {cool:.0f}C", hud.font_xs, t["text_med"],
                       (cx - 60 - hud.font_xs.size(f"H2O {cool:.0f}C")[0], cy + 60))

    # ── Widget — continuous scroll ──
    wly = cy + 82
    widget_h = H - wly - 24

    active = widgets.get_active(hud, music)
    if not active:
        return

    n = len(active)
    now_t = time.time()
    if n > 1 and now_t - _last_scroll_time > _SCROLL_INTERVAL:
        _last_scroll_time = now_t
        _scroll_idx += 1
        _scroll_target = _scroll_idx * widget_h

    # Animate
    if _scroll_offset < _scroll_target:
        _scroll_offset = min(_scroll_offset + _SCROLL_SPEED, _scroll_target)

    # Reset when cycled through all
    if _scroll_idx >= n:
        _scroll_offset = 0
        _scroll_target = 0
        _scroll_idx = 0
        _last_scroll_time = now_t

    # Clip and draw
    clip = pygame.Rect(6, wly, W - 12, widget_h)
    old_clip = s.get_clip()
    s.set_clip(clip)

    for i in range(n + 1):
        idx = i % n
        wname, mod = active[idx]
        slot_y = wly + i * widget_h - _scroll_offset
        if slot_y + widget_h < wly or slot_y > wly + widget_h:
            continue
        try:
            mod.draw(hud, 6, slot_y, W - 12, widget_h, music)
        except Exception:
            pass

    s.set_clip(old_clip)
