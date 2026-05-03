"""Honda Accord Hybrid HV Battery Widget
Shows pack SOC, voltage, power flow, cell health, and trend graphs.
Only active when OBD is connected. High priority — critical driving data.
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

# 2014 Accord Hybrid: 72 cells, 12 modules of 6 cells
MODULES = 12
CELLS_PER_MODULE = 6


def is_active(hud, music):
    try:
        with open("/tmp/car-hud-battery-data") as f:
            d = json.load(f)
        return d.get("connected", False) and time.time() - d.get("timestamp", 0) < 10
    except Exception:
        return False


def urgency(hud, music):
    """Promote when SOC is very low or health is poor."""
    try:
        with open("/tmp/car-hud-battery-data") as f:
            d = json.load(f)
        soc = d.get("soc", 50)
        health = d.get("health_score", 100)
        if soc < 15:
            return -150  # critical low SOC
        if health < 50:
            return -80   # poor health
    except Exception:
        pass
    return -5  # slightly above default when OBD connected


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t

    try:
        with open("/tmp/car-hud-battery-data") as f:
            d = json.load(f)
    except Exception:
        d = {}

    if not d.get("connected"):
        pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)
        lt = hud.font_sm.render("HV Battery — No Data", True, t["text_dim"])
        s.blit(lt, (x + w // 2 - lt.get_width() // 2, y + h // 2 - 6))
        return True

    soc = d.get("soc", 0)
    pack_v = d.get("pack_voltage", 0)
    power_kw = d.get("power_kw", 0)
    health = d.get("health_score", 100)
    cell_avg = d.get("cell_avg_v", 0)
    cell_delta = d.get("cell_delta_v", 0)
    is_regen = d.get("is_regen", False)
    is_charging = d.get("is_charging", False)
    discharge_rate = d.get("discharge_rate", 0)
    soc_rate = d.get("soc_rate", 0)
    regen_pct = d.get("session_regen_pct", 0)
    voltage_trend = d.get("voltage_trend", [])
    soc_trend = d.get("soc_trend", [])

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    # Layout depends on available height
    compact = h < 70

    if compact:
        _draw_compact(hud, s, t, x, y, w, h, d)
    else:
        _draw_full(hud, s, t, x, y, w, h, d)

    return True


def _draw_compact(hud, s, t, x, y, w, h, d):
    """Compact view — SOC bar + power flow + key stats."""
    soc = d.get("soc", 0)
    power_kw = d.get("power_kw", 0)
    health = d.get("health_score", 100)
    is_regen = d.get("is_regen", False)
    pack_v = d.get("pack_voltage", 0)

    cy = y + h // 2

    # Battery icon (left)
    bx, by = x + 8, cy - 10
    bw_icon, bh_icon = 24, 20

    # Battery body
    pygame.draw.rect(s, t["border"], (bx, by, bw_icon, bh_icon), border_radius=3)
    pygame.draw.rect(s, t["border"], (bx + bw_icon, by + 5, 3, 10))  # terminal

    # Fill based on SOC
    fill_color = GREEN if soc > 30 else AMBER if soc > 15 else RED
    fill_w = max(1, int((bw_icon - 4) * soc / 100))
    pygame.draw.rect(s, fill_color, (bx + 2, by + 2, fill_w, bh_icon - 4), border_radius=2)

    # SOC text
    soc_t = hud.font_md.render(f"{soc:.0f}%", True, t["text_bright"])
    s.blit(soc_t, (x + 38, cy - 10))

    # Power flow indicator
    if abs(power_kw) > 0.5:
        pw_color = GREEN if is_regen else t["primary"]
        pw_label = f"{abs(power_kw):.0f}kW {'⚡' if is_regen else '→'}"
        pw_t = hud.font_sm.render(pw_label, True, pw_color)
        s.blit(pw_t, (x + 38, cy + 6))

    # Pack voltage (right)
    vt = hud.font_sm.render(f"{pack_v:.0f}V", True, t["text_med"])
    s.blit(vt, (x + w - vt.get_width() - 10, cy - 10))

    # Health (right bottom)
    h_color = GREEN if health > 70 else AMBER if health > 40 else RED
    ht = hud.font_xs.render(f"H:{health}", True, h_color)
    s.blit(ht, (x + w - ht.get_width() - 10, cy + 6))


def _draw_full(hud, s, t, x, y, w, h, d):
    """Full view — battery visualization + trend graph + stats."""
    soc = d.get("soc", 0)
    pack_v = d.get("pack_voltage", 0)
    power_kw = d.get("power_kw", 0)
    health = d.get("health_score", 100)
    cell_avg = d.get("cell_avg_v", 0)
    cell_delta = d.get("cell_delta_v", 0)
    is_regen = d.get("is_regen", False)
    discharge_rate = d.get("discharge_rate", 0)
    soc_rate = d.get("soc_rate", 0)
    regen_pct = d.get("session_regen_pct", 0)
    voltage_trend = d.get("voltage_trend", [])
    soc_trend = d.get("soc_trend", [])

    # ── Left: Battery visualization ──
    left_w = w // 3
    cy = y + h // 2

    # Large battery icon with modules
    bx = x + 8
    by = y + 8
    bw_icon = left_w - 20
    bh_icon = h - 20

    # Battery outline
    pygame.draw.rect(s, t["border"], (bx, by, bw_icon, bh_icon), border_radius=4)
    pygame.draw.rect(s, t["border"], (bx + bw_icon // 4, by - 3, bw_icon // 2, 4))  # terminal

    # Draw 12 modules as horizontal bars inside battery
    mod_h = max(2, (bh_icon - 8) // MODULES - 1)
    for i in range(MODULES):
        mx = bx + 3
        my = by + 4 + i * (mod_h + 1)
        mw = bw_icon - 6

        # Module fill based on SOC + slight variance for visual interest
        mod_soc = soc + math.sin(i * 0.7) * cell_delta * 20
        mod_soc = max(0, min(100, mod_soc))
        fill = max(1, int(mw * mod_soc / 100))

        # Color: green→yellow→red based on individual module level
        if mod_soc > 50:
            mc = GREEN
        elif mod_soc > 25:
            mc = AMBER
        else:
            mc = RED

        pygame.draw.rect(s, mc, (mx, my, fill, mod_h), border_radius=1)

    # SOC overlay on battery
    soc_t = hud.font_lg.render(f"{soc:.0f}%", True, (255, 255, 255))
    soc_x = bx + (bw_icon - soc_t.get_width()) // 2
    soc_y = by + (bh_icon - soc_t.get_height()) // 2
    # Shadow for readability
    shadow = hud.font_lg.render(f"{soc:.0f}%", True, (0, 0, 0))
    s.blit(shadow, (soc_x + 1, soc_y + 1))
    s.blit(soc_t, (soc_x, soc_y))

    # ── Center: Stats ──
    cx = x + left_w + 4
    stat_w = w // 3 - 8

    stats = [
        (f"{pack_v:.0f}V", t["text_bright"]),
        (f"{cell_avg:.2f}V/cell", t["text_med"]),
    ]

    if abs(power_kw) > 0.5:
        pw_color = GREEN if is_regen else t["primary"]
        pw_label = f"{'↑' if is_regen else '↓'}{abs(power_kw):.0f}kW"
        stats.append((pw_label, pw_color))
    else:
        stats.append(("Idle", t["text_dim"]))

    h_color = GREEN if health > 70 else AMBER if health > 40 else RED
    stats.append((f"Health {health}", h_color))

    if regen_pct > 0:
        stats.append((f"Regen {regen_pct:.0f}%", GREEN))

    for i, (text, color) in enumerate(stats):
        if y + 8 + i * 16 > y + h - 4:
            break
        st = hud.font_xs.render(text, True, color)
        s.blit(st, (cx, y + 8 + i * 16))

    # ── Right: Mini trend graph ──
    gx = x + left_w + stat_w + 8
    gy = y + 8
    gw = w - left_w - stat_w - 16
    gh = h - 16

    if gw > 20 and gh > 20:
        # Graph background
        pygame.draw.rect(s, t["bg"], (gx, gy, gw, gh), border_radius=4)

        # Draw SOC trend line
        trend = soc_trend if soc_trend else voltage_trend
        if len(trend) > 2:
            min_v = min(trend)
            max_v = max(trend)
            if max_v - min_v < 1:
                max_v = min_v + 1

            points = []
            for i, val in enumerate(trend):
                px = gx + int(i / max(1, len(trend) - 1) * gw)
                py = gy + gh - int((val - min_v) / (max_v - min_v) * gh)
                py = max(gy + 1, min(gy + gh - 1, py))
                points.append((px, py))

            if len(points) > 1:
                pygame.draw.lines(s, t["primary"], False, points, 2)

            # Labels
            max_t = hud.font_mono.render(f"{max_v:.0f}", True, t["text_dim"])
            min_t = hud.font_mono.render(f"{min_v:.0f}", True, t["text_dim"])
            s.blit(max_t, (gx + 2, gy + 1))
            s.blit(min_t, (gx + 2, gy + gh - 10))

    return True
