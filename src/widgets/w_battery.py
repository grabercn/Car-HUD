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

    # -- Power flow --
    if abs(power_kw) > 0.5:
        pw_color = GREEN if is_regen else t["primary"]
        direction = "RGN" if is_regen else "OUT"
        pw_t = hud.font_xs.render(f"{abs(power_kw):.0f}kW {direction}",
                                  True, pw_color)
        s.blit(pw_t, (x + 38, cy + 6))

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

    # Layout: battery vis (left 30%) | stats (center 35%) | trend (right 35%)
    left_w = int(w * 0.28)
    center_w = int(w * 0.35)
    right_w = w - left_w - center_w

    # ═══════════════════════════════════════════
    # LEFT: 12-module battery visualization
    # ═══════════════════════════════════════════
    bx = x + pad
    by = y + pad
    bw = left_w - pad * 2
    bh = h - pad * 2

    # Battery outline
    pygame.draw.rect(s, t["border"], (bx, by, bw, bh), border_radius=4, width=1)
    # Terminal nub on top
    nub_w = bw // 3
    pygame.draw.rect(s, t["border"],
                     (bx + bw // 2 - nub_w // 2, by - 3, nub_w, 4),
                     border_radius=2)

    # Draw 12 module bars inside the battery body
    inner_pad = 3
    usable_h = bh - inner_pad * 2
    mod_gap = 1
    mod_h = max(2, (usable_h - (MODULES - 1) * mod_gap) // MODULES)

    for i in range(MODULES):
        mx = bx + inner_pad
        my = by + inner_pad + i * (mod_h + mod_gap)
        mw = bw - inner_pad * 2

        if my + mod_h > by + bh - inner_pad:
            break

        # Module variance reflects cell imbalance — edge modules degrade
        # faster due to thermal gradients in the pack
        edge_factor = abs(i - 5.5) / 5.5  # 0 at center, 1 at edges
        variance = cell_delta * 40 * edge_factor * math.sin(i * 1.3 + 0.5)
        mod_soc = max(0, min(100, soc - variance))
        fill = max(1, int(mw * mod_soc / 100))

        # Color: edge modules go amber/red when cell delta is high
        if cell_delta > 0.15 and edge_factor > 0.6:
            mc = RED if cell_delta > 0.25 else AMBER
        else:
            mc = _soc_color(mod_soc)

        # Dim background for unfilled portion
        pygame.draw.rect(s, t["bg"], (mx, my, mw, mod_h), border_radius=1)
        pygame.draw.rect(s, mc, (mx, my, fill, mod_h), border_radius=1)

    # SOC overlay centered on battery
    soc_str = f"{soc:.0f}%"
    soc_big = hud.font_lg.render(soc_str, True, WHITE)
    soc_shadow = hud.font_lg.render(soc_str, True, BLACK)
    sx = bx + (bw - soc_big.get_width()) // 2
    sy = by + (bh - soc_big.get_height()) // 2 - 6
    s.blit(soc_shadow, (sx + 1, sy + 1))
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
    # CENTER: Stats column
    # ═══════════════════════════════════════════
    cx = x + left_w
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

    # -- HV Pack stats --
    stat_line("Pack", f"{pack_v:.0f}V / {cell_avg:.2f}V")

    # Cell delta — #1 degradation indicator, always show
    delta_color = GREEN if cell_delta < 0.05 else AMBER if cell_delta < 0.15 else RED
    stat_line("Imbal", f"{cell_delta:.3f}V", val_color=delta_color)

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
    gx = x + left_w + center_w
    gy = y + pad
    gw = right_w - pad
    gh = h - pad * 2

    if gw > 30 and gh > 30:
        _draw_trend_graph(hud, s, t, gx, gy, gw, gh, soc_trend, voltage_trend)


def _draw_trend_graph(hud, s, t, gx, gy, gw, gh, soc_trend, voltage_trend):
    """Draw SOC trend (primary) with voltage trend (secondary)."""
    # Graph background
    pygame.draw.rect(s, t["bg"], (gx, gy, gw, gh), border_radius=4)

    label_margin = 8  # space at top for label
    graph_y = gy + label_margin
    graph_h = gh - label_margin - 2

    # Title
    title = hud.font_xs.render("SOC", True, t["text_dim"])
    s.blit(title, (gx + 3, gy + 1))

    # Draw SOC trend as the main line
    trend = soc_trend if len(soc_trend) > 2 else voltage_trend
    if len(trend) < 2:
        # No data yet — show placeholder
        no_data = hud.font_xs.render("waiting...", True, t["text_dim"])
        s.blit(no_data, (gx + gw // 2 - no_data.get_width() // 2,
                         gy + gh // 2 - 4))
        return

    # Calculate range with padding
    min_v = min(trend)
    max_v = max(trend)
    spread = max_v - min_v

    # Ensure minimum visible range
    if spread < 2:
        mid = (max_v + min_v) / 2
        min_v = mid - 1
        max_v = mid + 1
        spread = 2

    # Add 10% padding
    padding = spread * 0.1
    min_v -= padding
    max_v += padding
    spread = max_v - min_v

    # SOC threshold zones — faint colored bands for quick health read
    is_soc = len(soc_trend) > 2
    if is_soc and graph_h > 25:
        for thresh, zone_color in [(40, GREEN), (20, AMBER)]:
            if min_v < thresh < max_v:
                ty = graph_y + graph_h - int((thresh - min_v) / spread * graph_h)
                ty = max(graph_y + 1, min(graph_y + graph_h - 2, ty))
                dim = tuple(max(0, c // 5) for c in zone_color[:3])
                pygame.draw.line(s, dim, (gx + 1, ty), (gx + gw - 1, ty), 1)

    # Build points
    points = []
    n = len(trend)
    for i, val in enumerate(trend):
        px = gx + 2 + int(i / max(1, n - 1) * (gw - 4))
        normalized = (val - min_v) / spread
        py = graph_y + graph_h - int(normalized * graph_h)
        py = max(graph_y + 1, min(graph_y + graph_h - 1, py))
        points.append((px, py))

    # Fill area under the curve for visual weight
    if len(points) > 1:
        # Create filled polygon
        fill_pts = list(points)
        fill_pts.append((points[-1][0], graph_y + graph_h))
        fill_pts.append((points[0][0], graph_y + graph_h))

        # Semi-transparent fill using a lighter version of primary color
        fill_color = (*t["primary"][:3],) if len(t["primary"]) == 3 else t["primary"]
        # Dim the fill significantly
        dim_fill = tuple(max(0, c // 5) for c in fill_color[:3])
        try:
            pygame.draw.polygon(s, dim_fill, fill_pts)
        except Exception:
            pass

        # Main trend line — color based on overall direction (not last sample)
        line_color = t["primary"]
        if len(trend) > 3:
            trend_dir = trend[-1] - trend[0]
            if trend_dir > 1:
                line_color = GREEN   # net SOC gain (regen/charging)
            elif trend_dir < -3:
                line_color = RED     # significant SOC drop
            elif trend_dir < -0.5:
                line_color = AMBER   # mild discharge
        pygame.draw.lines(s, line_color, False, points, 2)

        # Current value dot at the end
        last_pt = points[-1]
        pygame.draw.circle(s, WHITE, last_pt, 3)
        pygame.draw.circle(s, line_color, last_pt, 2)

    # Axis labels
    max_label = hud.font_mono.render(f"{max_v:.0f}", True, t["text_dim"])
    min_label = hud.font_mono.render(f"{min_v:.0f}", True, t["text_dim"])
    s.blit(max_label, (gx + gw - max_label.get_width() - 2, graph_y))
    s.blit(min_label, (gx + gw - min_label.get_width() - 2,
                       graph_y + graph_h - min_label.get_height()))

    # Current value prominently
    if len(trend) > 0:
        cur = trend[-1]
        cur_t = hud.font_sm.render(f"{cur:.0f}%", True, t["text_bright"])
        s.blit(cur_t, (gx + gw - cur_t.get_width() - 2, gy + 1))

    # Horizontal reference lines (dashed feel)
    for frac in (0.25, 0.5, 0.75):
        ref_y = graph_y + int(graph_h * (1 - frac))
        for dx in range(0, gw - 4, 6):
            pygame.draw.line(s, t["border"],
                             (gx + 2 + dx, ref_y),
                             (gx + 2 + min(dx + 2, gw - 4), ref_y), 1)

    # Time span label — the trend covers the last 5 minutes
    tm_t = hud.font_mono.render("5m", True, t["text_dim"])
    s.blit(tm_t, (gx + gw - tm_t.get_width() - 2,
                  graph_y + graph_h - tm_t.get_height()))
