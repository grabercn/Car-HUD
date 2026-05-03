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
_HIGHLIGHT_FRAMES = 10  # frames to show border on newly-appeared widgets


def _draw_pin_icon(s, t, x, y):
    """Draw a small pin icon at (x, y)."""
    pygame.draw.circle(s, t["primary"], (x, y + 3), 4)
    pygame.draw.line(s, t["primary"], (x, y + 7), (x, y + 14), 2)
    pygame.draw.circle(s, t["primary"], (x, y + 14), 1)


def draw(hud, obd, music):
    W, H = hud.width, hud.height
    s = hud.surf
    t = hud.t
    vd = hud.smooth_data
    now_t = time.time()
    now = datetime.datetime.now()

    rpm = vd.get("RPM") or 0
    speed_raw = (vd.get("SPEED") or 0) * 0.621371
    load = vd.get("ENGINE_LOAD") or 0
    throttle = vd.get("THROTTLE_POS") or 0
    fuel = vd.get("FUEL_LEVEL")       # None when not yet read
    hv = vd.get("HYBRID_BATTERY_REMAINING")  # None when not yet read
    cool = vd.get("COOLANT_TEMP")     # None when not yet read
    volts = vd.get("CONTROL_MODULE_VOLTAGE")  # None when not yet read
    intake = vd.get("INTAKE_TEMP")    # None when not yet read
    ev = rpm < 100

    # Velocity prediction — damped extrapolation between OBD readings
    if not hasattr(draw, '_prev_speed'):
        draw._prev_speed = 0
        draw._speed_rate = 0
        draw._prev_t = now_t
    dt = now_t - draw._prev_t
    if 0 < dt < 1:
        raw_rate = (speed_raw - draw._prev_speed) / dt  # mph/sec
        draw._speed_rate += (raw_rate - draw._speed_rate) * 0.3  # smooth the rate
    elif dt >= 1:
        draw._speed_rate = 0  # stale — reset
    draw._prev_speed = speed_raw
    draw._prev_t = now_t
    # Clamp prediction to avoid overshoot; only predict when actually moving
    if speed_raw > 1:
        speed = max(0, speed_raw + draw._speed_rate * 0.016)
    else:
        speed = speed_raw

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
    if ev:
        # EV mode — show a thin green ring at zero fill to indicate electric drive
        hud.draw_arc_gauge(cx, cy, 97, 4, 0.0, GREEN,
                           start=math.pi * 1.15, end=-math.pi * 0.15)
    else:
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

    lx, ly, lr = 78, 148, 65
    if ev:
        hud.draw_arc_gauge(lx, ly, lr, 10, min(throttle / 100, 1.0), GREEN,
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

    rx, ry, rr = W - 78, 148, 65
    fuel_val = fuel if fuel is not None else 0
    hv_val = hv if hv is not None else 0
    if fuel is not None:
        fc = GREEN if fuel_val > 20 else AMBER if fuel_val > 10 else RED
        hud.draw_arc_gauge(rx, ry, rr, 10, fuel_val / 100, fc,
                           start=math.pi * 0.3, end=-math.pi * 0.3, ticks=True)
    else:
        # No data yet — draw empty track only
        hud.draw_arc_gauge(rx, ry, rr, 10, 0.0, t["border"],
                           start=math.pi * 0.3, end=-math.pi * 0.3, ticks=True)
    if hv is not None:
        bc = GREEN if hv_val > 30 else AMBER if hv_val > 15 else RED
        hud.draw_arc_gauge(rx, ry, rr - 18, 6, hv_val / 100, bc,
                           start=math.pi * 0.3, end=-math.pi * 0.3)
    else:
        hud.draw_arc_gauge(rx, ry, rr - 18, 6, 0.0, t["border"],
                           start=math.pi * 0.3, end=-math.pi * 0.3)
    fuel_lbl_c = t["text_dim"] if fuel is not None else t["border"]
    batt_lbl_c = t["text_dim"] if hv is not None else t["border"]
    hud.draw_glow_text("FUEL", hud.font_xs, fuel_lbl_c, (rx - 15, ry - rr - 14))
    hud.draw_glow_text("BATT", hud.font_xs, batt_lbl_c, (rx - 15, ry + rr + 4))

    ty = 6 + wy_off
    time_str = now.strftime("%I:%M").lstrip("0")  # strip leading zero from 12h time
    hud.draw_glow_text(time_str, hud.font_md, t["text_bright"], (12, ty))
    if volts is not None and volts > 0:
        vl = f"{volts:.1f}V"
        hud.draw_glow_text(vl, hud.font_md, t["text_med"],
                           (W - hud.font_md.size(vl)[0] - 12, ty))
    else:
        vl = "--V"
        hud.draw_glow_text(vl, hud.font_md, t["text_dim"],
                           (W - hud.font_md.size(vl)[0] - 12, ty))
    # AIR (intake temp) — show "--" when data not yet available
    if intake is not None and intake > 0:
        air_str = f"{intake:.0f}C"
        hud.draw_glow_text("AIR", hud.font_xs, t["text_dim"], (cx + 60, cy + 60))
        hud.draw_glow_text(air_str, hud.font_xs, t["text_dim"],
                           (cx + 60 + hud.font_xs.size("AIR ")[0], cy + 60))
    else:
        hud.draw_glow_text("AIR --", hud.font_xs, t["border"], (cx + 60, cy + 60))
    # H2O (coolant temp) — show "--" when data not yet available
    if cool is not None and cool > 0:
        h2o_str = f"H2O {cool:.0f}C"
        h2o_c = RED if cool > 110 else AMBER if cool > 100 else t["text_med"]
        hud.draw_glow_text(h2o_str, hud.font_xs, h2o_c,
                           (cx - 60 - hud.font_xs.size(h2o_str)[0], cy + 60))
    else:
        h2o_str = "H2O --"
        hud.draw_glow_text(h2o_str, hud.font_xs, t["border"],
                           (cx - 60 - hud.font_xs.size(h2o_str)[0], cy + 60))

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
        draw._last_top2 = []
        draw._last_n = n
        draw._resetting = False
        draw._widget_age = {}  # name -> frames since first appeared
        draw._pop_frames = 0   # remaining frames of pop-in slide effect

    # Track widget ages (frames since first appearance)
    active_names = {name for name, _ in active}
    for name in active_names:
        draw._widget_age[name] = draw._widget_age.get(name, 0) + 1
    for name in list(draw._widget_age):
        if name not in active_names:
            del draw._widget_age[name]

    # If widget count changed mid-scroll, clamp offset and smooth-reset
    if n != draw._last_n:
        max_off = max(0, (n - 1) * wh)
        draw._offset = min(draw._offset, max_off)
        draw._target = min(draw._target, max_off)
        draw._resetting = True
        draw._target = 0
        draw._last_n = n

    # Interrupt: top-2 priority order changed (new song, radar alert, etc.)
    # Checks both top widget AND runner-up so promotions to #2 also trigger
    top2 = [w[0] for w in active[:2]]
    if top2 != draw._last_top2:
        draw._last_top2 = top2
        draw._resetting = True
        draw._target = 0
        draw._pause_end = now_t + getattr(active[0][1], "view_time", 6)
        draw._pop_frames = 4  # trigger slide-up pop effect

    # Current widget's view_time for pause
    cur_wi = int(draw._offset / wh) % n if wh > 0 else 0
    pause = getattr(active[cur_wi][1], "view_time", 6)

    # Phase: resetting (smooth scroll-back), pausing, or scrolling forward
    if draw._resetting:
        draw._offset = max(draw._offset - _SCROLL_PX * 2, 0.0)
        if draw._offset <= 0:
            draw._offset = 0.0
            draw._target = 0
            draw._resetting = False
            draw._pause_end = now_t + pause
    elif draw._offset >= draw._target:
        if now_t >= draw._pause_end:
            draw._target += wh
    else:
        draw._offset = min(draw._offset + _SCROLL_PX, draw._target)
        if draw._offset >= draw._target:
            draw._pause_end = now_t + pause

    # Pop-in effect: slide up from 8px below over 4 frames, plus border flash
    pop_offset = 0
    pop_border = False
    if draw._pop_frames > 0:
        pop_offset = draw._pop_frames * 2  # 8, 6, 4, 2 px slide-up
        pop_border = draw._pop_frames >= 3  # border flash for first 2 frames
        draw._pop_frames -= 1

    # Clip and draw
    clip = pygame.Rect(6, wly, W - 12, wh)
    old_clip = s.get_clip()
    s.set_clip(clip)

    offset = int(draw._offset)
    for i in range(n * 2):
        wi = i % n
        slot_y = wly + i * wh - offset + pop_offset
        if slot_y > wly + wh:
            break
        if slot_y + wh < wly:
            continue
        try:
            active[wi][1].draw(hud, 6, slot_y, W - 12, wh, music)
            # Pop-in border flash (primary color, 2 frames)
            if pop_border:
                pygame.draw.rect(s, t["primary"],
                                 (6, slot_y, W - 12, wh), 2)
            # Highlight border for newly-appeared widgets
            age = draw._widget_age.get(active[wi][0], _HIGHLIGHT_FRAMES + 1)
            if age <= _HIGHLIGHT_FRAMES and not pop_border:
                pygame.draw.rect(s, t["primary"],
                                 (6, slot_y, W - 12, wh), 1)
            # Pin icon
            wname = active[wi][0].lower()
            if wname in (widgets.get_pinned() or []):
                _draw_pin_icon(s, t, W - 20, slot_y + 4)
        except Exception:
            pass

    s.set_clip(old_clip)

    # Reset on full cycle
    if draw._offset >= n * wh:
        draw._offset = 0.0
        draw._target = 0
        draw._resetting = False
        draw._pause_end = now_t + pause
