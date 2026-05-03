"""Honda Accord Hybrid HV Battery Widget
Shows real SOC, voltage, power flow, cell health, fuel level, and trend graphs.
Reads real data from battery monitor + OBD data files.
"""

import json
import time
import math
import pygame

name = "HV Battery"
priority = 3  # very high — critical vehicle data
view_time = 15
show_every = 0  # always available when OBD connected

GREEN = (0, 180, 85)
AMBER = (220, 160, 0)
RED = (220, 45, 45)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# 2014 Accord Hybrid: 72 cells, 12 modules of 6 cells
MODULES = 12
CELLS_PER_MODULE = 6

BATTERY_FILE = "/tmp/car-hud-battery-data"
OBD_FILE = "/tmp/car-hud-obd-data"

# Cache to avoid re-reading files every frame
_cache = {"bat": {}, "obd": {}, "bat_mt": 0, "obd_mt": 0}


def _read_data():
    """Read both battery and OBD data files with caching."""
    import os
    now = time.time()

    # Battery data
    try:
        mt = os.path.getmtime(BATTERY_FILE)
        if mt != _cache["bat_mt"]:
            with open(BATTERY_FILE) as f:
                _cache["bat"] = json.load(f)
            _cache["bat_mt"] = mt
    except Exception:
        pass

    # OBD data — for FUEL_LEVEL, COOLANT_TEMP, CONTROL_MODULE_VOLTAGE
    try:
        mt = os.path.getmtime(OBD_FILE)
        if mt != _cache["obd_mt"]:
            with open(OBD_FILE) as f:
                _cache["obd"] = json.load(f)
            _cache["obd_mt"] = mt
    except Exception:
        pass

    bat = _cache["bat"]
    obd_raw = _cache["obd"]

    # Merge OBD direct readings into a flat dict
    obd = obd_raw.get("data", {})
    fresh_bat = now - bat.get("timestamp", 0) < 10
    fresh_obd = now - obd_raw.get("timestamp", 0) < 10

    return bat, obd, fresh_bat, fresh_obd


def is_active(hud, music):
    bat, obd, fresh_bat, fresh_obd = _read_data()
    return bat.get("connected", False) and fresh_bat


def urgency(hud, music):
    """Promote when SOC is very low or health is poor."""
    bat = _cache.get("bat", {})
    soc = bat.get("soc", 50)
    health = bat.get("health_score", 100)
    if soc < 15:
        return -150  # critical low SOC
    if health < 50:
        return -80   # poor health
    return -5  # slightly above default when OBD connected


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t

    bat, obd, fresh_bat, fresh_obd = _read_data()

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    if not bat.get("connected") or not fresh_bat:
        lt = hud.font_sm.render("HV Battery -- No Data", True, t["text_dim"])
        s.blit(lt, (x + w // 2 - lt.get_width() // 2, y + h // 2 - 6))
        return True

    compact = h < 70
    if compact:
        _draw_compact(hud, s, t, x, y, w, h, bat, obd)
    else:
        _draw_full(hud, s, t, x, y, w, h, bat, obd)

    return True


# ── Helpers ──

def _soc_color(soc):
    """Color for SOC value."""
    if soc > 30:
        return GREEN
    if soc > 15:
        return AMBER
    return RED


def _health_color(health):
    """Color for health score."""
    if health > 70:
        return GREEN
    if health > 40:
        return AMBER
    return RED


def _fuel_color(fuel):
    """Color for fuel level."""
    if fuel > 30:
        return GREEN
    if fuel > 15:
        return AMBER
    return RED


def _draw_mini_bar(s, x, y, w, h, pct, color, bg_color, radius=2):
    """Draw a small filled progress bar."""
    pygame.draw.rect(s, bg_color, (x, y, w, h), border_radius=radius)
    fill_w = max(1, int(w * max(0, min(100, pct)) / 100))
    if fill_w > 0:
        pygame.draw.rect(s, color, (x, y, fill_w, h), border_radius=radius)


# ── Compact Mode ──

def _draw_compact(hud, s, t, x, y, w, h, bat, obd):
    """Compact: SOC bar + power + fuel + key stats in one row."""
    soc = bat.get("soc", 0)
    power_kw = bat.get("power_kw", 0)
    is_regen = bat.get("is_regen", False)
    health = bat.get("health_score", 100)
    pack_v = bat.get("pack_voltage", 0)
    fuel = obd.get("FUEL_LEVEL", -1)
    voltage_12v = obd.get("CONTROL_MODULE_VOLTAGE", 0)

    cy = y + h // 2

    # -- Battery icon (left) --
    bx, by = x + 8, cy - 10
    bw_icon, bh_icon = 24, 20

    pygame.draw.rect(s, t["border"], (bx, by, bw_icon, bh_icon), border_radius=3)
    pygame.draw.rect(s, t["border"], (bx + bw_icon, by + 5, 3, 10))  # terminal

    fill_color = _soc_color(soc)
    fill_w = max(1, int((bw_icon - 4) * soc / 100))
    pygame.draw.rect(s, fill_color, (bx + 2, by + 2, fill_w, bh_icon - 4),
                     border_radius=2)

    # -- SOC % --
    soc_t = hud.font_md.render(f"{soc:.0f}%", True, t["text_bright"])
    s.blit(soc_t, (x + 38, cy - 10))

    # -- Power flow with directional arrow --
    if abs(power_kw) > 0.5:
        pw_color = GREEN if is_regen else t["primary"]
        arrow = "<<" if is_regen else ">>"
        label = "RGN" if is_regen else "OUT"
        pw_t = hud.font_xs.render(f"{arrow} {abs(power_kw):.0f}kW {label}",
                                  True, pw_color)
        s.blit(pw_t, (x + 38, cy + 6))
    else:
        idle_t = hud.font_xs.render("-- IDLE", True, t["text_dim"])
        s.blit(idle_t, (x + 38, cy + 6))

    # -- Center: fuel bar if available --
    mid_x = x + w // 2 - 30
    if fuel > 0:
        fuel_label = hud.font_xs.render(f"Fuel {fuel:.0f}%", True,
                                        _fuel_color(fuel))
        s.blit(fuel_label, (mid_x, cy - 8))
        _draw_mini_bar(s, mid_x, cy + 6, 60, 5, fuel,
                       _fuel_color(fuel), t["border"])

    # -- Right side: voltage + health --
    rx = x + w - 10
    if pack_v > 0:
        vt = hud.font_sm.render(f"{pack_v:.0f}V", True, t["text_med"])
        s.blit(vt, (rx - vt.get_width(), cy - 10))

    ht = hud.font_xs.render(f"H:{health}", True, _health_color(health))
    s.blit(ht, (rx - ht.get_width(), cy + 6))


# ── Full Mode ──

def _draw_full(hud, s, t, x, y, w, h, bat, obd):
    """Full: battery visualization + real stats + trend graph."""
    soc = bat.get("soc", 0)
    pack_v = bat.get("pack_voltage", 0)
    power_kw = bat.get("power_kw", 0)
    health = bat.get("health_score", 100)
    cell_avg = bat.get("cell_avg_v", 0)
    cell_delta = bat.get("cell_delta_v", 0)
    is_regen = bat.get("is_regen", False)
    is_charging = bat.get("is_charging", False)
    discharge_rate = bat.get("discharge_rate", 0)
    soc_rate = bat.get("soc_rate", 0)
    regen_pct = bat.get("session_regen_pct", 0)
    session_min = bat.get("session_min_soc", soc)
    session_max = bat.get("session_max_soc", soc)
    voltage_trend = bat.get("voltage_trend", [])
    soc_trend = bat.get("soc_trend", [])
    speed = bat.get("speed", 0)
    rpm = bat.get("rpm", 0)
    ignition = bat.get("ignition", True)

    # OBD direct readings
    fuel = obd.get("FUEL_LEVEL", -1)
    coolant = obd.get("COOLANT_TEMP", -1)
    voltage_12v = obd.get("CONTROL_MODULE_VOLTAGE", 0)

    pad = 6
    inner_x = x + pad
    inner_w = w - pad * 2

    # Layout: battery vis (left) | flow arrow | stats (center) | trend (right)
    left_w = int(w * 0.28)
    flow_w = 26  # narrow animated power flow column
    center_w = int(w * 0.35)
    right_w = w - left_w - flow_w - center_w

    # ═══════════════════════════════════════════
    # LEFT: 12-module battery visualization
    # ═══════════════════════════════════════════
    bx = x + pad
    by = y + pad
    bw = left_w - pad * 2
    bh = h - pad * 2

    # Battery outline — subtle glow when charging/regen
    outline_color = t["border"]
    if is_regen or is_charging:
        glow_color = tuple(min(255, c + 40) for c in GREEN[:3])
        glow_dim = tuple(c // 3 for c in glow_color[:3])
        pygame.draw.rect(s, glow_dim,
                         (bx - 2, by - 2, bw + 4, bh + 4),
                         border_radius=6, width=1)
        pygame.draw.rect(s, glow_dim,
                         (bx - 1, by - 1, bw + 2, bh + 2),
                         border_radius=5, width=1)
        outline_color = glow_color
    pygame.draw.rect(s, outline_color, (bx, by, bw, bh),
                     border_radius=4, width=1)

    # Terminal nub — proportional to body (width ~20%, height ~4%)
    nub_w = max(6, bw // 5)
    nub_h = max(3, bh // 25)
    pygame.draw.rect(s, outline_color,
                     (bx + bw // 2 - nub_w // 2, by - nub_h, nub_w, nub_h + 1),
                     border_radius=2)

    # Draw 12 module bars inside the battery body
    inner_pad = 3
    # Reserve tiny space for top/bottom module labels
    label_h = 8  # height for "1" / "12" labels
    usable_h = bh - inner_pad * 2 - label_h * 2
    mod_gap = 1
    mod_h = max(2, (usable_h - (MODULES - 1) * mod_gap) // MODULES)
    modules_top = by + inner_pad + label_h

    # Pre-compute per-module health scores to find worst module
    mod_scores = []
    for i in range(MODULES):
        edge_factor = abs(i - 5.5) / 5.5  # 0 at center, 1 at edges
        variance = cell_delta * 40 * edge_factor * math.sin(i * 1.3 + 0.5)
        mod_soc = max(0, min(100, soc - variance))
        # Health gradient: blend SOC + cell balance into a 0-100 health
        mod_health = max(0, min(100, mod_soc - abs(variance) * 2))
        mod_scores.append((mod_soc, mod_health, variance, edge_factor))

    # Identify worst module(s) when cell_delta > 0.1V
    worst_threshold = cell_delta > 0.1
    if worst_threshold and mod_scores:
        worst_health = min(ms[1] for ms in mod_scores)
    else:
        worst_health = 100

    # Top label: "1"
    lbl_1 = hud.font_mono.render("1", True, t["text_dim"])
    s.blit(lbl_1, (bx + inner_pad, modules_top - label_h))

    for i in range(MODULES):
        mx = bx + inner_pad
        my = modules_top + i * (mod_h + mod_gap)
        mw = bw - inner_pad * 2

        if my + mod_h > by + bh - inner_pad - label_h:
            break

        mod_soc, mod_health, variance, edge_factor = mod_scores[i]
        fill = max(1, int(mw * mod_soc / 100))

        # Health gradient color: green -> amber -> red based on module health
        if mod_health > 70:
            mc = GREEN
        elif mod_health > 40:
            # Lerp green -> amber
            ratio = (mod_health - 40) / 30.0
            mc = (int(GREEN[0] + (AMBER[0] - GREEN[0]) * (1 - ratio)),
                  int(GREEN[1] + (AMBER[1] - GREEN[1]) * (1 - ratio)),
                  int(GREEN[2] + (AMBER[2] - GREEN[2]) * (1 - ratio)))
        else:
            # Lerp amber -> red
            ratio = max(0, mod_health) / 40.0
            mc = (int(AMBER[0] + (RED[0] - AMBER[0]) * (1 - ratio)),
                  int(AMBER[1] + (RED[1] - AMBER[1]) * (1 - ratio)),
                  int(AMBER[2] + (RED[2] - AMBER[2]) * (1 - ratio)))

        # Highlight worst module(s) with contrasting bright white border
        is_worst = (worst_threshold and mod_health <= worst_health + 2)

        # Dim background for unfilled portion
        pygame.draw.rect(s, t["bg"], (mx, my, mw, mod_h), border_radius=1)
        pygame.draw.rect(s, mc, (mx, my, fill, mod_h), border_radius=1)

        # Worst-module highlight: bright outline to draw attention
        if is_worst:
            pygame.draw.rect(s, WHITE, (mx, my, mw, mod_h),
                             border_radius=1, width=1)

    # Bottom label: "12"
    lbl_12 = hud.font_mono.render("12", True, t["text_dim"])
    lbl_12_y = modules_top + min(MODULES, 12) * (mod_h + mod_gap) - mod_gap
    s.blit(lbl_12, (bx + inner_pad, min(lbl_12_y, by + bh - inner_pad - label_h)))

    # ── Factory reference bar (thin, right edge of battery column) ──
    factory_soc_min = bat.get("factory_soc_min", 20)
    factory_soc_max = bat.get("factory_soc_max", 80)
    ref_x = bx + bw + 3
    ref_w = 5
    if ref_x + ref_w < x + left_w:
        # Full bar outline (dim)
        pygame.draw.rect(s, t["border"], (ref_x, by, ref_w, bh),
                         border_radius=1, width=1)
        # Factory operating range band (20-80%)
        fac_top = by + inner_pad + int(usable_h * (1 - factory_soc_max / 100))
        fac_bot = by + inner_pad + int(usable_h * (1 - factory_soc_min / 100))
        fac_h = max(1, fac_bot - fac_top)
        fac_color = tuple(max(0, c // 3) for c in GREEN[:3])
        pygame.draw.rect(s, fac_color, (ref_x + 1, fac_top, ref_w - 2, fac_h))
        # Current SOC tick mark (bright)
        cur_y = by + inner_pad + int(usable_h * (1 - soc / 100))
        cur_y = max(by + 1, min(by + bh - 2, cur_y))
        pygame.draw.line(s, WHITE, (ref_x, cur_y), (ref_x + ref_w, cur_y), 2)
        # Tiny "F" label
        f_label = hud.font_mono.render("F", True, t["text_dim"])
        s.blit(f_label, (ref_x, by + bh + 1))

    # SOC overlay centered on battery — multi-layer shadow for readability
    soc_str = f"{soc:.0f}%"
    soc_big = hud.font_lg.render(soc_str, True, WHITE)
    soc_shadow = hud.font_lg.render(soc_str, True, BLACK)
    soc_mid = hud.font_lg.render(soc_str, True, (30, 30, 30))
    sx = bx + (bw - soc_big.get_width()) // 2
    sy = by + (bh - soc_big.get_height()) // 2 - 6
    # Three-layer shadow: outer dark spread, mid penumbra, bright text
    s.blit(soc_shadow, (sx + 2, sy + 2))
    s.blit(soc_mid, (sx + 1, sy + 1))
    s.blit(soc_shadow, (sx - 1, sy + 1))
    s.blit(soc_big, (sx, sy))

    # Power flow label under SOC
    if abs(power_kw) > 0.3:
        if is_regen:
            pw_str = f"+{abs(power_kw):.0f}kW RGN"
            pw_color = GREEN
        else:
            pw_str = f"-{abs(power_kw):.0f}kW"
            pw_color = t["primary"]
    else:
        pw_str = "IDLE"
        pw_color = t["text_dim"]

    pw_t = hud.font_xs.render(pw_str, True, pw_color)
    pw_shadow = hud.font_xs.render(pw_str, True, BLACK)
    px = bx + (bw - pw_t.get_width()) // 2
    py = sy + soc_big.get_height() + 1
    s.blit(pw_shadow, (px + 1, py + 1))
    s.blit(pw_t, (px, py))

    # ═══════════════════════════════════════════
    # FLOW: Animated power flow indicator column
    # ═══════════════════════════════════════════
    _draw_flow_indicator(hud, s, t, x + left_w, y + pad, flow_w, h - pad * 2,
                         power_kw, is_regen)

    # ═══════════════════════════════════════════
    # CENTER: Stats column
    # ═══════════════════════════════════════════
    cx = x + left_w + flow_w
    cy_start = y + pad
    line_h = 15
    row = 0

    def stat_line(label, value, color=t["text_med"], val_color=None):
        nonlocal row
        ly = cy_start + row * line_h
        if ly + line_h > y + h - pad:
            return
        if val_color is None:
            val_color = color
        lt = hud.font_xs.render(label, True, t["text_dim"])
        vt = hud.font_xs.render(str(value), True, val_color)
        s.blit(lt, (cx, ly))
        s.blit(vt, (cx + center_w - vt.get_width() - pad, ly))
        row += 1

    def stat_header(text, color=t["text_bright"]):
        nonlocal row
        ly = cy_start + row * line_h
        if ly + line_h > y + h - pad:
            return
        ht = hud.font_sm.render(text, True, color)
        s.blit(ht, (cx, ly))
        row += 1

    # -- Health score as visual bar --
    factory_health = bat.get("factory_health", 100)
    h_color = _health_color(health)
    ly = cy_start + row * line_h
    if ly + line_h < y + h - pad:
        hl = hud.font_xs.render(f"Health {health}", True, h_color)
        s.blit(hl, (cx, ly))
        bar_x = cx + hl.get_width() + 3
        bar_w = cx + center_w - pad - bar_x
        if bar_w > 8:
            _draw_mini_bar(s, bar_x, ly + 3, bar_w, 5,
                           health, h_color, t["border"], radius=2)
        row += 1
    # Factory health context (dim)
    fh_ly = cy_start + row * line_h
    if fh_ly + line_h < y + h - pad:
        fh_t = hud.font_mono.render(
            f"New: {factory_health}  Now: {health}", True, t["text_dim"])
        s.blit(fh_t, (cx, fh_ly))
        row += 1

    # -- HV Pack stats --
    stat_line("Pack", f"{pack_v:.0f}V / {cell_avg:.2f}V")

    # Cell delta — #1 degradation indicator, always show
    factory_cell_delta = bat.get("factory_cell_delta", 0.02)
    delta_color = GREEN if cell_delta < 0.05 else AMBER if cell_delta < 0.15 else RED
    stat_line("Imbal", f"{cell_delta:.3f}V", val_color=delta_color)
    # Factory cell delta reference (dim)
    fd_ly = cy_start + row * line_h
    if fd_ly + line_h < y + h - pad:
        fd_t = hud.font_mono.render(
            f"vs {factory_cell_delta:.3f}V new", True, t["text_dim"])
        s.blit(fd_t, (cx, fd_ly))
        row += 1

    # Capacity estimate: SOC%/mile (lower = healthier pack)
    cap_per_mi = bat.get("capacity_soc_per_mi", 0)
    if cap_per_mi > 0:
        cap_color = GREEN if cap_per_mi < 2 else AMBER if cap_per_mi < 4 else RED
        stat_line("Cap", f"{cap_per_mi:.1f}%/mi", val_color=cap_color)

    # Regen recovery rate: SOC%/min during regen (higher = healthier)
    regen_recov = bat.get("regen_recovery_rate", 0)
    if regen_recov > 0:
        rr_color = GREEN if regen_recov > 1.0 else AMBER if regen_recov > 0.4 else RED
        stat_line("Rgn Rcv", f"{regen_recov:.1f}%/m", val_color=rr_color)
    elif regen_pct > 0:
        stat_line("Regen", f"{regen_pct:.0f}%", val_color=GREEN)

    # SOC rate
    if abs(soc_rate) > 0.01:
        rate_color = GREEN if soc_rate > 0 else AMBER
        stat_line("Rate", f"{soc_rate:+.1f}%/min", val_color=rate_color)

    # Session SOC range (shrinking over time = degradation)
    if session_max > session_min + 1:
        stat_line("Range", f"{session_min:.0f}-{session_max:.0f}%")
        # Factory operating range reference (dim)
        fr_ly = cy_start + row * line_h
        if fr_ly + line_h < y + h - pad:
            fr_t = hud.font_mono.render(
                f"vs {factory_soc_min:.0f}-{factory_soc_max:.0f}% new",
                True, t["text_dim"])
            s.blit(fr_t, (cx, fr_ly))
            row += 1

    # -- 12V / Fuel section --
    # Separator
    row += 0.3  # tiny gap

    if fuel > 0 or voltage_12v > 0:
        stat_header("VEHICLE", t["primary"])

    if fuel > 0:
        stat_line("Fuel", f"{fuel:.0f}%", val_color=_fuel_color(fuel))
        # Mini fuel bar
        bar_y = cy_start + int(row * line_h) - 2
        if bar_y + 5 < y + h - pad:
            _draw_mini_bar(s, cx, bar_y, center_w - pad * 2, 4,
                           fuel, _fuel_color(fuel), t["border"])
            row += 0.4

    if voltage_12v > 0:
        v12_color = GREEN if voltage_12v > 12.4 else AMBER if voltage_12v > 11.8 else RED
        stat_line("12V Batt", f"{voltage_12v:.1f}V", val_color=v12_color)

    if coolant > 0:
        cool_color = GREEN if coolant < 100 else AMBER if coolant < 110 else RED
        stat_line("Coolant", f"{coolant}C", val_color=cool_color)

    # ═══════════════════════════════════════════
    # RIGHT: Trend graph
    # ═══════════════════════════════════════════
    gx = x + left_w + flow_w + center_w
    gy = y + pad
    gw = right_w - pad
    gh = h - pad * 2

    if gw > 30 and gh > 30:
        health_trend = bat.get("health_trend", [])
        _draw_trend_graph(hud, s, t, gx, gy, gw, gh, soc_trend, voltage_trend,
                          health=health, health_trend=health_trend,
                          session_min_soc=session_min, session_max_soc=session_max)

    # ── Subtle replacement hint (bottom-right corner, barely visible) ──
    hint = bat.get("replacement_hint")
    if hint:
        _draw_replacement_hint(hud, s, t, x, y, w, h, hint)


def _draw_replacement_hint(hud, s, t, x, y, w, h, hint):
    """Tiny dot + one word in bottom-right corner. Deliberately unobtrusive."""
    # Color mapping: dim enough to ignore while driving
    if hint == "Soon":
        dot_color = (180, 40, 40)       # small red dot
        text_color = (140, 40, 40)      # dim red text
    elif hint == "Plan":
        dot_color = (180, 130, 0)       # amber dot
        text_color = (160, 120, 0)      # slightly brighter amber text
    else:  # "Monitor"
        dot_color = (160, 120, 0)       # amber dot
        text_color = (120, 90, 0)       # dim amber text

    label = hud.font_xs.render(hint, True, text_color)
    lw = label.get_width()
    lh = label.get_height()

    # Position: bottom-right corner, inset by padding
    tx = x + w - lw - 8
    ty = y + h - lh - 4

    # Tiny dot to the left of the text
    dot_x = tx - 7
    dot_y = ty + lh // 2
    pygame.draw.circle(s, dot_color, (dot_x, dot_y), 2)

    s.blit(label, (tx, ty))


def _draw_flow_indicator(hud, s, t, fx, fy, fw, fh, power_kw, is_regen):
    """Draw animated power flow arrow between battery and stats columns.

    Discharging: arrow pointing RIGHT (OUT), primary color
    Regenerating: arrow pointing LEFT (RGN), green
    Idle: dim dash
    """
    cx = fx + fw // 2
    cy = fy + fh // 2

    if abs(power_kw) > 0.3:
        # Active flow — animated arrow
        now = time.time()
        # Cycle offset: 0..1 repeating every 0.8s
        phase = (now % 0.8) / 0.8

        if is_regen:
            # Arrow pointing LEFT (into battery)
            color = GREEN
            label = "RGN"
            # Arrow tip moves left; phase 0=right, 1=left
            offset = int((1 - phase) * 8) - 4  # -4..+4 px horizontal bounce
            tip_x = cx - 5 + offset
            # Arrowhead pointing left
            pygame.draw.line(s, color, (cx + 6, cy), (tip_x, cy), 2)
            pygame.draw.line(s, color, (tip_x, cy), (tip_x + 3, cy - 3), 2)
            pygame.draw.line(s, color, (tip_x, cy), (tip_x + 3, cy + 3), 2)
        else:
            # Arrow pointing RIGHT (out of battery)
            color = t["primary"]
            label = "OUT"
            offset = int(phase * 8) - 4  # -4..+4 px horizontal bounce
            tip_x = cx + 5 + offset
            # Arrowhead pointing right
            pygame.draw.line(s, color, (cx - 6, cy), (tip_x, cy), 2)
            pygame.draw.line(s, color, (tip_x, cy), (tip_x - 3, cy - 3), 2)
            pygame.draw.line(s, color, (tip_x, cy), (tip_x - 3, cy + 3), 2)

        # Power value above arrow
        kw_t = hud.font_mono.render(f"{abs(power_kw):.0f}", True, color)
        s.blit(kw_t, (cx - kw_t.get_width() // 2, cy - 14))

        # Label below arrow
        lb_t = hud.font_mono.render(label, True, color)
        s.blit(lb_t, (cx - lb_t.get_width() // 2, cy + 6))
    else:
        # Idle — small dim dash
        color = t["text_dim"]
        pygame.draw.line(s, color, (cx - 4, cy), (cx + 4, cy), 1)
        idle_t = hud.font_mono.render("--", True, color)
        s.blit(idle_t, (cx - idle_t.get_width() // 2, cy + 6))


def _draw_trend_graph(hud, s, t, gx, gy, gw, gh, soc_trend, voltage_trend,
                      health=100, health_trend=None, session_min_soc=0,
                      session_max_soc=100):
    """Draw SOC trend (primary) with voltage overlay (secondary), grid lines,
    session marker, min/max labels, and health direction arrow."""
    if health_trend is None:
        health_trend = []

    # Graph background
    pygame.draw.rect(s, t["bg"], (gx, gy, gw, gh), border_radius=4)

    label_margin = 14  # space at top for title row
    bottom_margin = 14  # space at bottom for time span pill
    graph_y = gy + label_margin
    graph_h = gh - label_margin - bottom_margin

    # ── [6] Title with health direction arrow ──
    title_str = "SOC Trend"
    if len(health_trend) >= 2:
        h_dir = health_trend[-1] - health_trend[0]
        if h_dir < -1:
            title_str += " \u2193"  # down arrow — health declining
        elif h_dir > 1:
            title_str += " \u2191"  # up arrow — health improving
    elif health < 70:
        title_str += " \u2193"  # low health fallback
    title = hud.font_sm.render(title_str, True, t["text_bright"])
    s.blit(title, (gx + 3, gy + 1))

    # ── Check for data ──
    has_soc = len(soc_trend) > 2
    trend = soc_trend if has_soc else voltage_trend
    if len(trend) < 2:
        no_data = hud.font_xs.render("waiting...", True, t["text_dim"])
        s.blit(no_data, (gx + gw // 2 - no_data.get_width() // 2,
                         gy + gh // 2 - 4))
        return

    # ── SOC range calculation ──
    min_v = min(trend)
    max_v = max(trend)
    spread = max_v - min_v

    if spread < 2:
        mid = (max_v + min_v) / 2
        min_v = mid - 1
        max_v = mid + 1
        spread = 2

    padding_v = spread * 0.1
    min_v -= padding_v
    max_v += padding_v
    spread = max_v - min_v

    # Helper: value -> y coordinate
    def val_to_y(val):
        normalized = (val - min_v) / spread
        py = graph_y + graph_h - int(normalized * graph_h)
        return max(graph_y + 1, min(graph_y + graph_h - 1, py))

    # Helper: index -> x coordinate
    def idx_to_x(i, n):
        return gx + 2 + int(i / max(1, n - 1) * (gw - 4))

    # ── [2] Grid lines at 25%, 50%, 75% SOC ──
    if has_soc and graph_h > 25:
        grid_color = tuple(max(0, c // 4) for c in t["border"][:3])
        for soc_level in (25, 50, 75):
            if min_v < soc_level < max_v:
                gy_line = val_to_y(soc_level)
                pygame.draw.line(s, grid_color,
                                 (gx + 2, gy_line), (gx + gw - 2, gy_line), 1)
                gl = hud.font_mono.render(f"{soc_level}", True, t["text_dim"])
                s.blit(gl, (gx + 3, gy_line - gl.get_height()))

    # SOC threshold zones — faint colored bands for quick health read
    if has_soc and graph_h > 25:
        for thresh, zone_color in [(40, GREEN), (20, AMBER)]:
            if min_v < thresh < max_v:
                ty = val_to_y(thresh)
                dim = tuple(max(0, c // 5) for c in zone_color[:3])
                pygame.draw.line(s, dim, (gx + 1, ty), (gx + gw - 1, ty), 1)

    # ── [4] Session start marker (vertical dashed line) ──
    if len(trend) > 10:
        marker_x = gx + 2
        dash_color = tuple(max(0, c // 3) for c in t["accent"][:3])
        for dy in range(0, graph_h, 5):
            y1 = graph_y + dy
            y2 = min(graph_y + dy + 2, graph_y + graph_h)
            pygame.draw.line(s, dash_color, (marker_x, y1), (marker_x, y2), 1)

    # ── Build SOC points ──
    points = []
    n = len(trend)
    for i, val in enumerate(trend):
        points.append((idx_to_x(i, n), val_to_y(val)))

    # ── Fill area under SOC curve ──
    if len(points) > 1:
        fill_pts = list(points)
        fill_pts.append((points[-1][0], graph_y + graph_h))
        fill_pts.append((points[0][0], graph_y + graph_h))

        fill_color = (*t["primary"][:3],) if len(t["primary"]) == 3 else t["primary"]
        dim_fill = tuple(max(0, c // 5) for c in fill_color[:3])
        try:
            pygame.draw.polygon(s, dim_fill, fill_pts)
        except Exception:
            pass

        # Main SOC line — color based on overall direction
        line_color = t["primary"]
        if len(trend) > 3:
            trend_dir = trend[-1] - trend[0]
            if trend_dir > 1:
                line_color = GREEN
            elif trend_dir < -3:
                line_color = RED
            elif trend_dir < -0.5:
                line_color = AMBER
        pygame.draw.lines(s, line_color, False, points, 2)

        # Current value dot
        last_pt = points[-1]
        pygame.draw.circle(s, WHITE, last_pt, 3)
        pygame.draw.circle(s, line_color, last_pt, 2)

    # ── [1] Voltage trend as second trace (dimmed accent) ──
    if has_soc and len(voltage_trend) > 2:
        v_min = min(voltage_trend)
        v_max = max(voltage_trend)
        v_spread = v_max - v_min
        if v_spread < 1:
            v_mid = (v_max + v_min) / 2
            v_min = v_mid - 0.5
            v_max = v_mid + 0.5
            v_spread = 1.0
        v_pad = v_spread * 0.1
        v_min -= v_pad
        v_max += v_pad
        v_spread = v_max - v_min

        vn = len(voltage_trend)
        v_points = []
        for i, val in enumerate(voltage_trend):
            vx = idx_to_x(i, vn)
            v_norm = (val - v_min) / v_spread
            vy = graph_y + graph_h - int(v_norm * graph_h)
            vy = max(graph_y + 1, min(graph_y + graph_h - 1, vy))
            v_points.append((vx, vy))

        if len(v_points) > 1:
            v_color = tuple(max(0, c * 2 // 3) for c in t["accent"][:3])
            pygame.draw.lines(s, v_color, False, v_points, 1)

        # Small "V" label near the last voltage point
        if v_points:
            vl = hud.font_mono.render("V", True, t["accent"])
            vlx = min(v_points[-1][0] + 2, gx + gw - vl.get_width() - 1)
            vly = max(graph_y, min(graph_y + graph_h - vl.get_height(),
                                   v_points[-1][1] - vl.get_height() // 2))
            s.blit(vl, (vlx, vly))

    # ── [5] Min/max labels on the right edge ──
    if has_soc:
        data_min = min(soc_trend)
        data_max = max(soc_trend)
        min_y = val_to_y(data_min)
        max_y = val_to_y(data_max)

        max_lbl = hud.font_mono.render(f"{data_max:.0f}", True, t["text_bright"])
        min_lbl = hud.font_mono.render(f"{data_min:.0f}", True, t["text_dim"])

        rx = gx + gw - max_lbl.get_width() - 2
        max_ly = max(graph_y, max_y - max_lbl.get_height())
        min_ly = min(graph_y + graph_h - min_lbl.get_height(), min_y + 1)

        # Avoid overlap between min and max labels
        if min_ly - max_ly < max_lbl.get_height() + 2:
            max_ly = graph_y
            min_ly = graph_y + graph_h - min_lbl.get_height()

        s.blit(max_lbl, (rx, max_ly))
        s.blit(min_lbl, (rx, min_ly))
    else:
        # Voltage-only fallback: show axis range
        max_label = hud.font_mono.render(f"{max_v:.0f}", True, t["text_dim"])
        min_label = hud.font_mono.render(f"{min_v:.0f}", True, t["text_dim"])
        s.blit(max_label, (gx + gw - max_label.get_width() - 2, graph_y))
        s.blit(min_label, (gx + gw - min_label.get_width() - 2,
                           graph_y + graph_h - min_label.get_height()))

    # Current value prominently at top-right
    if len(trend) > 0:
        cur = trend[-1]
        unit = "%" if has_soc else "V"
        cur_t = hud.font_sm.render(f"{cur:.0f}{unit}", True, t["text_bright"])
        s.blit(cur_t, (gx + gw - cur_t.get_width() - 2, gy + 1))

    # Horizontal reference lines (dashed) at 25/50/75% of graph height
    for frac in (0.25, 0.5, 0.75):
        ref_y = graph_y + int(graph_h * (1 - frac))
        for dx in range(0, gw - 4, 6):
            pygame.draw.line(s, t["border"],
                             (gx + 2 + dx, ref_y),
                             (gx + 2 + min(dx + 2, gw - 4), ref_y), 1)

    # ── [3] Time span label — prominent pill at bottom-center ──
    span_str = " 5m "
    tm_bg = tuple(max(0, c // 3) for c in t["primary"][:3])
    tm_t = hud.font_sm.render(span_str, True, t["text_bright"])
    tm_x = gx + (gw - tm_t.get_width()) // 2
    tm_y = gy + gh - bottom_margin + 1
    pill_rect = (tm_x - 2, tm_y, tm_t.get_width() + 4, tm_t.get_height())
    pygame.draw.rect(s, tm_bg, pill_rect, border_radius=3)
    s.blit(tm_t, (tm_x, tm_y))
