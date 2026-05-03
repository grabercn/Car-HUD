"""Mini-Map widget — GPS position, compass heading, and movement trail from Cobra RAD 700i."""

import json
import math
import time
import pygame

name = "Map"
priority = 40
view_time = 8

GREEN = (0, 180, 85)
AMBER = (220, 160, 0)

# Trail of recent positions: list of (lat, lon, timestamp)
_trail = []
_MAX_TRAIL = 30


def _read_gps():
    """Read shared GPS data written by the Cobra RAD 700i driver."""
    try:
        with open("/tmp/car-hud-gps") as f:
            d = json.load(f)
        if d.get("lat", 0) != 0 and d.get("lon", 0) != 0:
            return d
    except Exception:
        pass
    return None


def _heading_to_compass(deg):
    """Convert heading degrees to 8-point compass label."""
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int((deg + 22.5) % 360 / 45)
    return dirs[idx]


def is_active(hud, music):
    gps = _read_gps()
    return gps is not None


def urgency(hud, music):
    return 0


def _update_trail(gps):
    """Add current position to trail if it differs from the last point."""
    lat, lon = gps["lat"], gps["lon"]
    ts = gps.get("timestamp", time.time())
    # Only add if moved from last point (avoid duplicates when stationary)
    if _trail:
        last_lat, last_lon, _ = _trail[-1]
        if abs(lat - last_lat) < 1e-6 and abs(lon - last_lon) < 1e-6:
            return
    _trail.append((lat, lon, ts))
    if len(_trail) > _MAX_TRAIL:
        _trail.pop(0)


def _draw_compass(s, cx, cy, radius, heading, t):
    """Draw a visual compass indicator with heading needle."""
    # Outer ring
    pygame.draw.circle(s, t["border"], (cx, cy), radius, 1)
    # Tick marks at N/E/S/W
    for angle_deg, label in [(0, "N"), (90, "E"), (180, "S"), (270, "W")]:
        rad = math.radians(angle_deg)
        ox = cx + int((radius - 2) * math.sin(rad))
        oy = cy - int((radius - 2) * math.cos(rad))
        tick_len = 4
        ix = cx + int((radius - tick_len - 2) * math.sin(rad))
        iy = cy - int((radius - tick_len - 2) * math.cos(rad))
        pygame.draw.line(s, t["text_dim"], (ix, iy), (ox, oy), 1)

    # Heading needle
    h_rad = math.radians(heading)
    nx = cx + int((radius - 6) * math.sin(h_rad))
    ny = cy - int((radius - 6) * math.cos(h_rad))
    pygame.draw.line(s, GREEN, (cx, cy), (nx, ny), 2)
    # Small dot at needle tip
    pygame.draw.circle(s, GREEN, (nx, ny), 2)
    # Opposite side (tail) — dimmer, shorter
    tx = cx - int((radius // 2) * math.sin(h_rad))
    ty = cy + int((radius // 2) * math.cos(h_rad))
    pygame.draw.line(s, t["text_dim"], (cx, cy), (tx, ty), 1)


def _draw_trail(s, trail, cx, cy, area_w, area_h, t):
    """Draw trail dots scaled relative to each other within the given area."""
    if len(trail) < 2:
        return

    lats = [p[0] for p in trail]
    lons = [p[1] for p in trail]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    # Add padding so single-axis movement still renders
    span_lat = max(max_lat - min_lat, 1e-5)
    span_lon = max(max_lon - min_lon, 1e-5)

    margin = 8
    draw_w = area_w - margin * 2
    draw_h = area_h - margin * 2

    for i, (lat, lon, ts) in enumerate(trail):
        # Normalize to 0..1
        nx = (lon - min_lon) / span_lon
        ny = 1.0 - (lat - min_lat) / span_lat  # invert Y: north = up
        px = int(cx - draw_w // 2 + nx * draw_w)
        py = int(cy - draw_h // 2 + ny * draw_h)

        # Older dots are dimmer and smaller, newest is brightest
        age = i / max(len(trail) - 1, 1)  # 0=oldest, 1=newest
        r = max(1, int(1 + age * 3))
        alpha = int(80 + 175 * age)
        color = (0, min(alpha, 180), int(40 + 45 * age))
        pygame.draw.circle(s, color, (px, py), r)

    # Connecting lines between recent points (last 10) for direction clarity
    recent = trail[-min(10, len(trail)):]
    if len(recent) >= 2:
        for i in range(len(recent) - 1):
            lat1, lon1, _ = recent[i]
            lat2, lon2, _ = recent[i + 1]
            nx1 = (lon1 - min_lon) / span_lon
            ny1 = 1.0 - (lat1 - min_lat) / span_lat
            nx2 = (lon2 - min_lon) / span_lon
            ny2 = 1.0 - (lat2 - min_lat) / span_lat
            px1 = int(cx - draw_w // 2 + nx1 * draw_w)
            py1 = int(cy - draw_h // 2 + ny1 * draw_h)
            px2 = int(cx - draw_w // 2 + nx2 * draw_w)
            py2 = int(cy - draw_h // 2 + ny2 * draw_h)
            age_frac = (i + len(trail) - len(recent)) / max(len(trail) - 1, 1)
            line_c = (0, int(60 + 80 * age_frac), int(30 + 40 * age_frac))
            pygame.draw.line(s, line_c, (px1, py1), (px2, py2), 1)


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    gps = _read_gps()

    if not gps:
        # ── No GPS — graceful fallback ──
        cy = y + h // 2
        nt = hud.font_sm.render("No GPS", True, t["text_dim"])
        s.blit(nt, (x + w // 2 - nt.get_width() // 2, cy - 6))
        return True

    lat = gps.get("lat", 0)
    lon = gps.get("lon", 0)
    speed = gps.get("speed", 0)
    heading = gps.get("heading", 0)

    _update_trail(gps)

    compass_str = _heading_to_compass(heading)

    # ── Compact layout (h < 65): single row ──
    if h < 65:
        cy = y + h // 2

        # Compass direction label
        ct = hud.font_md.render(compass_str, True, GREEN)
        s.blit(ct, (x + 10, cy - ct.get_height() // 2))

        # Coords
        coord_str = f"{lat:.4f}, {lon:.4f}"
        lt = hud.font_xs.render(coord_str, True, t["text_med"])
        s.blit(lt, (x + 10 + ct.get_width() + 10, cy - 8))

        # Speed — right side
        if speed > 0:
            st = hud.font_md.render(f"{speed} mph", True, t["text_bright"])
            s.blit(st, (x + w - st.get_width() - 10, cy - st.get_height() // 2))
        else:
            st = hud.font_xs.render("0 mph", True, t["text_dim"])
            s.blit(st, (x + w - st.get_width() - 10, cy - 4))

        return True

    # ── Full layout ──
    # Left column: compass + text info
    left_w = w // 2

    # Compass indicator — centered in left column upper area
    compass_r = min(left_w // 2 - 12, (h - 30) // 2 - 8, 30)
    compass_cx = x + left_w // 2
    compass_cy = y + 8 + compass_r + 4
    _draw_compass(s, compass_cx, compass_cy, compass_r, heading, t)

    # Compass label inside circle
    cl = hud.font_sm.render(compass_str, True, GREEN)
    s.blit(cl, (compass_cx - cl.get_width() // 2, compass_cy - cl.get_height() // 2))

    # Heading degrees below compass
    deg_str = f"{heading}\u00b0"
    dt = hud.font_xs.render(deg_str, True, t["text_dim"])
    s.blit(dt, (compass_cx - dt.get_width() // 2, compass_cy + compass_r + 2))

    # Speed below heading
    info_y = compass_cy + compass_r + 14
    if speed > 0:
        spd_t = hud.font_md.render(f"{speed}", True, t["text_bright"])
        unit_t = hud.font_xs.render(" mph", True, t["text_dim"])
        total_w = spd_t.get_width() + unit_t.get_width()
        spd_x = x + left_w // 2 - total_w // 2
        s.blit(spd_t, (spd_x, info_y))
        s.blit(unit_t, (spd_x + spd_t.get_width(), info_y + spd_t.get_height() - unit_t.get_height()))
    else:
        zt = hud.font_xs.render("0 mph", True, t["text_dim"])
        s.blit(zt, (x + left_w // 2 - zt.get_width() // 2, info_y))

    # Coordinates below speed
    coord_y = info_y + 18
    lat_str = f"{lat:.5f}"
    lon_str = f"{lon:.5f}"
    lat_t = hud.font_xs.render(lat_str, True, t["text_med"])
    lon_t = hud.font_xs.render(lon_str, True, t["text_med"])
    s.blit(lat_t, (x + left_w // 2 - lat_t.get_width() // 2, coord_y))
    s.blit(lon_t, (x + left_w // 2 - lon_t.get_width() // 2, coord_y + 12))

    # Right column: trail map
    trail_cx = x + left_w + (w - left_w) // 2
    trail_cy = y + h // 2
    trail_w = w - left_w - 8
    trail_h = h - 12

    # Trail area border
    trail_x0 = trail_cx - trail_w // 2
    trail_y0 = trail_cy - trail_h // 2
    pygame.draw.rect(s, t["border"], (trail_x0, trail_y0, trail_w, trail_h), 1, border_radius=4)

    if len(_trail) >= 2:
        _draw_trail(s, _trail, trail_cx, trail_cy, trail_w, trail_h, t)
    else:
        # No trail yet
        wt = hud.font_xs.render("Building", True, t["text_dim"])
        wt2 = hud.font_xs.render("trail...", True, t["text_dim"])
        s.blit(wt, (trail_cx - wt.get_width() // 2, trail_cy - 10))
        s.blit(wt2, (trail_cx - wt2.get_width() // 2, trail_cy + 4))

    # Current position dot in trail (always centered when only 1 point)
    if len(_trail) == 1:
        pygame.draw.circle(s, GREEN, (trail_cx, trail_cy), 3)

    return True
