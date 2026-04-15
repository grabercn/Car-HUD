"""Vehicle page — OBD instrument cluster with music strip."""

import math
import datetime
import pygame

GREEN = (0, 180, 85)
AMBER = (220, 160, 0)
RED = (220, 45, 45)


def draw(hud, obd, music):
    """Draw the vehicle instrument cluster page."""
    W, H = hud.width, hud.height
    s = hud.surf
    t = hud.t
    vd = hud.smooth_data
    now = datetime.datetime.now()

    # Data extraction
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

    # Warnings and DTCs (at the very top)
    wy = 0
    all_warnings = (obd.get("warnings") or [])[:]
    for dtc in (obd.get("dtcs") or []):
        all_warnings.append(f"ENGINE CODE: {dtc}")
    for wt in all_warnings[:3]:
        txt = hud.font_sm.render(wt, True, RED)
        pygame.draw.rect(s, (25, 5, 5), (0, wy, W, txt.get_height() + 4))
        s.blit(txt, ((W - txt.get_width()) // 2, wy + 2))
        wy += txt.get_height() + 4

    # ── Central Cluster: Speedo ──
    cx, cy = W // 2, 148
    r_speed = 115
    sp_pct = min(speed / 140, 1.0)
    hud.draw_arc_gauge(cx, cy, r_speed, 14, sp_pct, t["primary"],
                       start=math.pi * 1.15, end=-math.pi * 0.15, ticks=True)

    # RPM as thin inner ring
    rpm_pct = min(rpm / 7000, 1.0)
    rc = t["primary_dim"] if rpm < 3000 else AMBER if rpm < 5500 else RED
    hud.draw_arc_gauge(cx, cy, r_speed - 18, 4, rpm_pct, rc,
                       start=math.pi * 1.15, end=-math.pi * 0.15)

    # Speed Digits
    sp_str = f"{int(speed)}"
    sp_pos = (cx - hud.font_xxl.size(sp_str)[0] // 2, cy - 65)
    hud.draw_glow_text(sp_str, hud.font_xxl, t["text_bright"], sp_pos)

    unit_str = "MPH"
    unit_pos = (cx - hud.font_md.size(unit_str)[0] // 2, cy - 2)
    hud.draw_glow_text(unit_str, hud.font_md, t["text_dim"], unit_pos)

    # EV/GAS status badge
    mc = GREEN if ev else t["primary"]
    badge_w, badge_h = 56, 22
    pygame.draw.rect(s, (0, 0, 0, 100),
                     (cx - badge_w // 2 - 1, cy + 28, badge_w + 2, badge_h + 2), border_radius=4)
    pygame.draw.rect(s, mc, (cx - badge_w // 2, cy + 29, badge_w, badge_h), border_radius=4)
    ml = hud.font_sm.render("EV" if ev else "GAS", True, (0, 0, 0))
    s.blit(ml, (cx - ml.get_width() // 2, cy + 29 + (badge_h - ml.get_height()) // 2))

    # ── Left Cluster: CHG/PWR ──
    lx, ly = 65, 148
    lr = 70
    if ev:
        pwr_pct = min(throttle / 80, 1.0)
        hud.draw_arc_gauge(lx, ly, lr, 10, pwr_pct, GREEN,
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

    # ── Right Cluster: Fuel & Battery ──
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

    # ── Top strip info ──
    ty = 6 + wy
    hud.draw_glow_text(now.strftime("%I:%M"), hud.font_md, t["text_bright"], (12, ty))
    vl_str = f"{volts:.1f}V"
    hud.draw_glow_text(vl_str, hud.font_md, t["text_med"],
                       (W - hud.font_md.size(vl_str)[0] - 12, ty))

    # ── Lower Data (between clusters) ──
    hud.draw_glow_text(f"AIR {intake:.0f}C", hud.font_xs, t["text_dim"],
                       (cx + 55, cy + 55))
    hud.draw_glow_text(f"H2O {cool:.0f}C", hud.font_xs, t["text_med"],
                       (cx - 55 - hud.font_xs.size(f"H2O {cool:.0f}C")[0], cy + 55))

    # ── Music strip — just below gauge labels ──
    ly = cy + 75
    pygame.draw.line(s, t["border_lite"], (10, ly), (W - 10, ly))
    hud.draw_lower_section(ly + 2, music, vd)
