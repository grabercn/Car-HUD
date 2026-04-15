"""Vehicle page — OBD instrument cluster with continuous scroll widget."""

import math
import time
import datetime
import pygame
import widgets

GREEN = (0, 180, 85)
AMBER = (220, 160, 0)
RED = (220, 45, 45)

_SCROLL_PX = 5  # pixels per frame


def draw(hud, obd, music):
    W, H = hud.width, hud.height
    s = hud.surf
    t = hud.t
    vd = hud.smooth_data
    now_t = time.time()
    now = datetime.datetime.now()

    rpm = vd.get("RPM", 0)
    speed_raw = vd.get("SPEED", 0) * 0.621371
    load = vd.get("ENGINE_LOAD", 0)
    throttle = vd.get("THROTTLE_POS", 0)
    fuel = vd.get("FUEL_LEVEL", 0)
    hv = vd.get("HYBRID_BATTERY_REMAINING", 0)
    cool = vd.get("COOLANT_TEMP", 0)
    volts = vd.get("CONTROL_MODULE_VOLTAGE", 0)
    intake = vd.get("INTAKE_TEMP", 0)
    ev = rpm < 100

    # Velocity prediction — extrapolate speed between OBD readings
    if not hasattr(draw, '_prev_speed'):
        draw._prev_speed = 0
        draw._speed_rate = 0
        draw._prev_t = now_t
    dt = now_t - draw._prev_t
    if dt > 0 and dt < 1:
        draw._speed_rate = (speed_raw - draw._prev_speed) / dt  # mph/sec
    draw._prev_speed = speed_raw
    draw._prev_t = now_t
    # Predict ahead by half a frame interval
    speed = max(0, speed_raw + draw._speed_rate * 0.03)

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
    # Static labels (cached by draw_glow_text)
    hud.draw_glow_text("PWR", hud.font_xs, t["text_dim"], (lx - 12, ly - lr - 14))
    hud.draw_glow_text("CHG", hud.font_xs, GREEN, (lx - 12, ly + lr + 4))

    rx, ry, rr = W - 65, 148, 70
    fc = GREEN if fuel > 20 else AMBER if fuel > 10 else RED
    hud.draw_arc_gauge(rx, ry, rr, 10, fuel / 100, fc, start=math.pi * 0.3, end=-math.pi * 0.3, ticks=True)
    bc = GREEN if hv > 30 else AMBER if hv > 15 else RED
    hud.draw_arc_gauge(rx, ry, rr - 18, 6, hv / 100, bc, start=math.pi * 0.3, end=-math.pi * 0.3)
    hud.draw_glow_text("FUEL", hud.font_xs, t["text_dim"], (rx - 15, ry - rr - 14))
    hud.draw_glow_text("BATT", hud.font_xs, t["text_dim"], (rx - 15, ry + rr + 4))

    ty = 6 + wy_off
    hud.draw_glow_text(now.strftime("%I:%M"), hud.font_md, t["text_bright"], (12, ty))
    vl = f"{volts:.1f}V"
    hud.draw_glow_text(vl, hud.font_md, t["text_med"], (W - hud.font_md.size(vl)[0] - 12, ty))
    hud.draw_glow_text(f"{intake:.0f}C", hud.font_xs, t["text_dim"], (cx + 60, cy + 60))
    hud.draw_glow_text(f"{cool:.0f}C", hud.font_xs, t["text_med"],
                       (cx - 60 - hud.font_xs.size(f"{cool:.0f}C")[0], cy + 60))

    # ── Widget — continuous scroll ──
    wly = cy + 96
    wh = H - wly - 4

    active = widgets.get_active(hud, music)
    if not active:
        return

    n = len(active)
    if n == 1:
        active[0][1].draw(hud, 6, wly, W - 12, wh, music)
        return

    if not hasattr(draw, '_offset'):
        draw._offset = 0.0
        draw._target = 0
        draw._pause_end = time.time() + 6
        draw._last_top = ""

    # Interrupt on priority change
    top_name = active[0][0] if active else ""
    if top_name != draw._last_top:
        draw._last_top = top_name
        draw._offset = 0.0
        draw._target = 0
        draw._pause_end = now_t + getattr(active[0][1], "view_time", 6)

    # Current widget's view_time for pause
    cur_wi = int(draw._offset / wh) % n if wh > 0 else 0
    pause = getattr(active[cur_wi][1], "view_time", 6)

    if draw._offset >= draw._target:
        if now_t >= draw._pause_end:
            draw._target += wh
    else:
        draw._offset = min(draw._offset + _SCROLL_PX, draw._target)
        if draw._offset >= draw._target:
            draw._pause_end = now_t + pause

    # Clip and draw
    clip = pygame.Rect(6, wly, W - 12, wh)
    old_clip = s.get_clip()
    s.set_clip(clip)

    offset = int(draw._offset)
    for i in range(n * 2):
        wi = i % n
        slot_y = wly + i * wh - offset
        if slot_y > wly + wh:
            break
        if slot_y + wh < wly:
            continue
        try:
            active[wi][1].draw(hud, 6, slot_y, W - 12, wh, music)
        except Exception:
            pass

    s.set_clip(old_clip)

    # Reset on full cycle
    if draw._offset >= n * wh:
        draw._offset = 0.0
        draw._target = 0
        draw._pause_end = now_t + pause
