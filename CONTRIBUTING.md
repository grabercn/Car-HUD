# Car-HUD Developer Guide

## Project Structure

```
Car-HUD/
├── src/
│   ├── config.py           # Shared constants, paths, utilities
│   ├── hud.py              # Main HUD display (pygame, rendering, events)
│   ├── obd_service.py      # OBD-II BLE adapter (Vgate iCar Pro 2S)
│   ├── cobra_service.py    # Cobra RAD 700i radar detector (BLE via pygatt)
│   ├── spotify_service.py  # Spotify Connect + API polling
│   ├── web_service.py      # Web server (settings, camera, terminal, APIs)
│   ├── wifi_service.py     # WiFi/tether management
│   ├── voice_service.py    # Voice control (Vosk STT + "Hey Honda")
│   ├── display_service.py  # PWM backlight brightness (GPIO 18)
│   ├── battery_monitor.py  # HV battery health tracking (SQLite)
│   ├── splash_service.py   # Boot splash screen
│   ├── touch_service.py    # Touchscreen input (evdev → gestures)
│   ├── brain.py            # Voice command processing (Gemini + local)
│   ├── intent.py           # Voice intent matching (keyword scoring)
│   ├── bt_autoconnect.sh   # Bluetooth phone auto-reconnect
│   ├── update.sh           # OTA updater (GitHub → Pi)
│   ├── pages/
│   │   ├── vehicle.py      # OBD instrument cluster page
│   │   └── system.py       # Widget dashboard page
│   └── widgets/
│       ├── __init__.py     # Widget discovery, config, pinning, cooldowns
│       ├── w_music.py      # Now playing (Spotify/BT audio)
│       ├── w_connectivity.py  # WiFi + Bluetooth status
│       ├── w_weather.py    # Weather via wttr.in (IP/GPS geolocation)
│       ├── w_battery.py    # HV battery health + trend graphs
│       ├── w_radar.py      # Cobra radar detector alerts
│       ├── w_camera.py     # Dashcam live preview
│       ├── w_system.py     # Uptime + disk usage
│       ├── w_dashcam.py    # Recording status
│       ├── w_trip.py       # Trip distance/speed/duration
│       └── w_recent.py     # Recently played tracks
├── services/               # systemd service files
└── CONTRIBUTING.md         # This file
```

## Adding a New Widget

Create `src/widgets/w_yourwidget.py`:

```python
\"\"\"Short description of what this widget shows.\"\"\"

import pygame

# Required attributes
name = "YourWidget"     # Display name
priority = 50           # Lower = shown first (0-99)
view_time = 6           # Seconds to display before rotating

# Optional attributes
show_every = 0          # Cooldown in seconds (0 = always available)
requires_online = False # Skip when no internet

def is_active(hud, music) -> bool:
    \"\"\"Return True if this widget has content to show.\"\"\"
    return True

def urgency(hud, music) -> int:
    \"\"\"Return negative number to temporarily promote priority.
    -100 = jump to front for 15 seconds (e.g., new song started).
    0 = normal priority.
    \"\"\"
    return 0

def draw(hud, x, y, w, h, music) -> bool:
    \"\"\"Render the widget within the given rect.

    Args:
        hud: CarHUD instance (access fonts, theme, surface via hud.surf)
        x, y: Top-left corner of widget area
        w, h: Width and height available
        music: Current music data dict

    Returns:
        True if content was drawn, False to skip.
    \"\"\"
    s = hud.surf
    t = hud.t  # current theme colors

    # Draw panel background
    pygame.draw.rect(s, t["panel"], (x, y, w, h), border_radius=6)

    # Draw your content
    text = hud.font_md.render("Hello", True, t["text_bright"])
    s.blit(text, (x + 10, y + h // 2 - 8))

    return True
```

The widget is auto-discovered on next restart. No registration needed.

## Adding a New Service

1. Create `src/yourservice.py`
2. Create `services/car-hud-yourservice.service`
3. Data exchange: write JSON to `/tmp/car-hud-yourdata`
4. Use `from config import PROJECT_DIR, log, write_signal`

## Theme Colors

Access via `hud.t["key"]`:

| Key | Purpose |
|-----|---------|
| `primary` | Main accent color (gauges, active indicators) |
| `primary_dim` | Dimmed version of primary |
| `accent` | Secondary accent |
| `bg` | Background color |
| `panel` | Widget panel background |
| `border` | Gauge track / borders |
| `border_lite` | Subtle divider lines |
| `text_bright` | Primary text (white-ish) |
| `text_med` | Secondary text |
| `text_dim` | Tertiary / labels |

## Voice Commands

Add intents to `src/intent.py` in the `INTENTS` dict:

```python
"your_intent": {
    "action": "your_action",
    "target": "your_target",
    "keywords": {"keyword": 3, "another": 2},
    "phrases": ["exact phrase match", "another phrase"],
},
```

Handle in `hud.py` under the voice signal processing section.

## Hardware Wiring

| Component | Pi Pin | GPIO |
|-----------|--------|------|
| Display PWM | Pin 12 | GPIO 18 |
| Display GND | Pin 14 | GND |
| Lux sensor VCC | Pin 2 | 5V |
| Lux sensor SDA | Pin 3 | GPIO 2 |
| Lux sensor SCL | Pin 5 | GPIO 3 |
| Lux sensor GND | Pin 6 | GND |

## Data Files

All services communicate via JSON files in `/tmp/`:

| File | Writer | Reader | Contents |
|------|--------|--------|----------|
| `car-hud-obd-data` | obd_service | hud, battery_monitor | RPM, speed, load, voltage |
| `car-hud-music-data` | spotify_service | hud, widgets | Track, artist, progress |
| `car-hud-cobra-data` | cobra_service | hud, widgets | Alert band, GPS |
| `car-hud-battery-data` | battery_monitor | hud, widgets | SOC, health, trends |
| `car-hud-wifi-data` | wifi_service | hud, widgets | SSID, IP, state |
| `car-hud-display-data` | display_service | web_service | Brightness, lux |
| `car-hud-gps` | cobra_service | weather widget | Lat, lon, speed |
| `car-hud-voice-signal` | voice_service | hud | Action, target, time |
| `car-hud-touch` | touch_service | hud | Gesture, x, y |
"""
