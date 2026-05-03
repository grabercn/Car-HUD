# Car-HUD

A Raspberry Pi-powered heads-up display for the 2014 Honda Accord Hybrid.
Voice-controlled, theme-aware, with live vehicle data, dashcam, and AI assistant.

![Last Commit](https://img.shields.io/github/last-commit/grabercn/Car-HUD)

> Auto-generated on 2026-05-03 by
> [`.github/scripts/generate_readmes.py`](.github/scripts/generate_readmes.py)

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Hardware Requirements](#hardware-requirements)
- [Quick Start](#quick-start)
- [Widgets](#widgets)
- [Services](#services)
- [Sub-READMEs](#sub-readmes)
- [Documentation](#documentation)
- [Contributing](#contributing)

---

## Features

- **HV Battery** -- Honda Accord Hybrid HV Battery Widget
- **Radar** -- Radar Detector widget -- Cobra RAD 700i alerts and status
- **Music** -- Music / Now Playing widget
- **Trip** -- Trip Computer widget — full session stats for 2014 Honda Accord Hybrid
- **Connectivity** -- Connectivity widget -- WiFi + Bluetooth unified
- **Dashcam** -- Dashcam status widget
- **Weather** -- Weather widget -- current conditions via wttr.in (no API key needed)
- **Recent** -- Recently Played widget -- shows last few tracks from Spotify
- **Map** -- Mini-Map widget -- GPS position, compass heading, and movement trail
- **Camera** -- Camera widget -- live feed preview from connected cameras
- **System** -- System Info widget -- uptime, disk usage, and version

---

## Architecture

```
 Phone (BT)         Cobra RAD 700i (BLE)        Vgate iCar Pro (BLE)
      |                       |                          |
      v                       v                          v
 music_service          cobra_service               obd_service
 spotify_service             |                          |
      |                      v                          v
      |               /tmp/car-hud-cobra     /tmp/car-hud-obd-data
      |                      |                          |
      v                      v                          v
 /tmp/car-hud-music   +-----------+   /tmp/car-hud-battery-data
                      |           |          ^
                      |  hud.py   |<---------+---- battery_monitor
                      |  (pygame) |
                      |           |-----> pages/  -----> widgets/
                      +-----------+
                           |
               +-----------+-----------+
               |           |           |
               v           v           v
          display     web_service   voice_service
         (TFT LCD)   (MJPEG/HTTP)  (Vosk + Gemini)
                                        |
                                        v
                                     brain.py
                                   (NLU + TTS)
```

---

## Hardware Requirements

| Component | Model |
|-----------|-------|
| Compute | Raspberry Pi 3B+ (1 GB RAM) |
| Display | 3.5" TFT 480x320 (1000 nits) |
| OBD-II | Vgate iCar Pro 2S (BT 5.2 LE) |
| Radar | Cobra RAD 700i (BLE + GPS) |
| Camera | Logitech C925e (dashcam + mic) |
| Audio | AB13X USB sound card (lapel mic + speaker) |
| Storage | 64 GB SanDisk Ultra microSD |

---

## Quick Start

```bash
# Clone to Pi
git clone https://github.com/grabercn/Car-HUD.git
cd Car-HUD

# Install everything (services, deps, permissions)
sudo bash scripts/install.sh

# Reboot to start all services
sudo reboot
```

---

## Widgets

| Widget | Priority | View Time | Show Every | Online? |
|--------|----------|-----------|------------|---------|
| HV Battery | 3 | 15s | 0s | No |
| Radar | 5 | 15s | 0s | No |
| Music | 10 | 12s | 0s | No |
| Trip | 10 | 12s | 0s | No |
| Connectivity | 15 | 5s | 60s | No |
| Dashcam | 15 | 6s | 0s | No |
| Weather | 25 | 6s | 180s | Yes |
| Recent | 30 | 10s | 0s | Yes |
| Map | 40 | 8s | 0s | No |
| Camera | 50 | 8s | 90s | No |
| System | 99 | 4s | 120s | No |

> Lower priority = shown first. See [`src/widgets/README.md`](src/widgets/README.md) for full details.

---

## Services

| Unit File | Description |
|-----------|-------------|
| `car-hud-battery.service` | Car-HUD Honda Hybrid Battery Monitor |
| `car-hud-cobra.service` | Car-HUD Cobra RAD 700i Radar Detector |
| `car-hud-dashcam.service` | Honda Accord Dashcam |
| `car-hud-display.service` | Car-HUD Display Brightness Controller |
| `car-hud-music.service` | Car-HUD Bluetooth Music Service |
| `car-hud-obd.service` | Honda Accord OBD-II Monitor |
| `car-hud-splash.service` | Honda Accord Boot Splash |
| `car-hud-touch.service` | Car-HUD Touch Input Service |
| `car-hud-updater.service` | Car-HUD Auto Updater |
| `car-hud-voice.service` | Honda Accord Voice Commands |
| `car-hud-web.service` | Car-HUD Screenshot Server |
| `car-hud-wifi.service` | Honda Accord WiFi Manager |
| `car-hud.service` | Honda Accord HUD |
| `hide-cursor.service` | Hide mouse cursor |

> See [`services/README.md`](services/README.md) for full details.

---

## Sub-READMEs

| Path | Contents |
|------|----------|
| [`src/README.md`](src/README.md) | All source modules with docstring descriptions |
| [`src/widgets/README.md`](src/widgets/README.md) | Widget files with priority, timing, and stats |
| [`services/README.md`](services/README.md) | Systemd unit files with descriptions |

---

## Documentation

Full project docs are published at **https://grabercn.github.io/Car-HUD/**

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for guidelines on code style, testing,
and pull-request workflow.
