"""Weather widget — current conditions via wttr.in (no API key needed)."""

import json
import time
import threading
import pygame

name = "Weather"
priority = 25
view_time = 6
requires_online = True
show_every = 180  # show once every 3 minutes — data doesn't change fast

_data = {"temp": "", "desc": "", "icon": "", "city": "", "last_fetch": 0, "ok": False}
_fetching = False


def _get_location():
    """Get GPS from shared GPS file (Cobra, future GPS module, etc)."""
    try:
        with open("/tmp/car-hud-gps") as f:
            d = json.load(f)
        lat = d.get("lat", 0)
        lon = d.get("lon", 0)
        if lat != 0 and lon != 0 and time.time() - d.get("timestamp", 0) < 300:
            return f"{lat},{lon}"
    except Exception:
        pass
    return ""  # fall back to IP geolocation


def _fetch_weather():
    """Fetch weather — uses Cobra GPS if available, else IP geolocation."""
    global _fetching
    if _fetching:
        return
    _fetching = True
    try:
        import urllib.request
        loc = _get_location()
        url = f"https://wttr.in/{loc}?format=j1" if loc else "https://wttr.in/?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "Car-HUD/1.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        d = json.loads(resp.read())

        current = d.get("current_condition", [{}])[0]
        area = d.get("nearest_area", [{}])[0]

        _data["temp"] = current.get("temp_F", "")
        _data["desc"] = current.get("weatherDesc", [{}])[0].get("value", "")
        _data["humidity"] = current.get("humidity", "")
        _data["wind"] = current.get("windspeedMiles", "")
        _data["city"] = area.get("areaName", [{}])[0].get("value", "")
        _data["region"] = area.get("region", [{}])[0].get("value", "")
        _data["ok"] = True
        _data["last_fetch"] = time.time()
    except Exception as e:
        # Write error so we can debug
        try:
            with open("/tmp/car-hud-weather-error", "w") as f:
                f.write(str(e))
        except:
            pass
    _fetching = False


def is_active(hud, music):
    # Trigger fetch if needed
    if _data["last_fetch"] == 0:
        # First time — try synchronous, fall back to background
        _fetch_weather()
        if not _data["ok"]:
            # Mark as attempted so we don't block every frame
            _data["last_fetch"] = time.time()
    elif time.time() - _data["last_fetch"] > 300:
        # Refresh every 5 min in background
        threading.Thread(target=_fetch_weather, daemon=True).start()
    return _data["ok"]


def urgency(hud, music):
    return 0


def draw(hud, x, y, w, h, music):
    s = hud.surf
    t = hud.t

    if not _data["ok"]:
        # Show loading state instead of blank
        pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)
        lt = hud.font_sm.render("Loading weather...", True, t["text_dim"])
        s.blit(lt, (x + w // 2 - lt.get_width() // 2, y + h // 2 - 6))
        return True

    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    temp = _data.get("temp", "")
    desc = _data.get("desc", "")
    city = _data.get("city", "")
    humidity = _data.get("humidity", "")
    wind = _data.get("wind", "")

    cy = y + h // 2

    # Weather icon — simple shapes, no border_radius on ellipse
    import math
    ix, iy = x + 20, cy
    dl = desc.lower()
    if "sun" in dl or "clear" in dl:
        pygame.draw.circle(s, (255, 200, 50), (ix, iy), 8)
        for angle_deg in range(0, 360, 45):
            rad = math.radians(angle_deg)
            pygame.draw.line(s, (255, 200, 50),
                             (ix + int(10 * math.cos(rad)), iy + int(10 * math.sin(rad))),
                             (ix + int(14 * math.cos(rad)), iy + int(14 * math.sin(rad))), 2)
    elif "cloud" in dl or "overcast" in dl or "partly" in dl:
        pygame.draw.ellipse(s, t["text_med"], (ix - 10, iy - 6, 20, 12))
        pygame.draw.ellipse(s, t["text_med"], (ix - 5, iy - 10, 14, 10))
    elif "rain" in dl or "drizzle" in dl:
        pygame.draw.ellipse(s, t["text_med"], (ix - 10, iy - 8, 20, 10))
        for dx in [-4, 0, 4]:
            pygame.draw.line(s, t["primary"], (ix + dx, iy + 4), (ix + dx - 1, iy + 9), 2)
    elif "snow" in dl:
        for angle_deg in [0, 60, 120]:
            rad = math.radians(angle_deg)
            pygame.draw.line(s, (200, 220, 255),
                             (ix - int(8 * math.cos(rad)), iy - int(8 * math.sin(rad))),
                             (ix + int(8 * math.cos(rad)), iy + int(8 * math.sin(rad))), 2)
    else:
        pygame.draw.circle(s, (255, 200, 50), (ix - 3, iy - 4), 6)
        pygame.draw.ellipse(s, t["text_med"], (ix - 6, iy - 2, 16, 10))

    # Temperature — big and bold
    tx = x + 42
    if temp:
        tt = hud.font_lg.render(f"{temp}°F", True, t["text_bright"])
        s.blit(tt, (tx, cy - 16))

    # Description + location
    if desc:
        dt = hud.font_xs.render(desc, True, t["text_med"])
        s.blit(dt, (tx, cy + 12))

    # Right side: humidity + wind + city
    rx = x + w - 10
    if city:
        ct = hud.font_xs.render(city, True, t["text_dim"])
        s.blit(ct, (rx - ct.get_width(), cy - 10))
    details = []
    if humidity:
        details.append(f"{humidity}%")
    if wind:
        details.append(f"{wind}mph")
    if details:
        dt = hud.font_xs.render("  ".join(details), True, t["text_dim"])
        s.blit(dt, (rx - dt.get_width(), cy + 6))

    return True
