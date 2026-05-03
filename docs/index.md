# Car-HUD

**A Raspberry Pi-powered head-up display for the 2014 Honda Accord Hybrid.**

Built on a Pi 3B+ with a 2.5" 480x320 TFT display, Car-HUD provides real-time vehicle data, music control, radar detection, and smart widgets — all controlled by touch and voice.

## Features

- **OBD-II Gauges** — Speed, RPM, power flow, fuel, HV battery via BLE adapter
- **HV Battery Monitor** — SOC, health score, voltage trends, historical tracking
- **Spotify Connect** — Now playing, album art, progress, device control
- **Cobra RAD 700i** — Radar/laser alerts with audio warnings and GPS
- **Weather** — Real-time conditions via GPS or IP geolocation
- **Dashcam** — Live preview, recording status, footage browser
- **Voice Control** — "Hey Honda" wake word with Vosk offline STT
- **Smart Widgets** — Auto-rotating, priority-based, pinnable, cooldown-aware
- **Web Interface** — Settings, camera feed, terminal, REST APIs
- **Touch Screen** — Tap to switch pages, swipe, long-press to pin
- **Auto Day/Night** — Theme switches based on time (future: lux sensor)
- **OTA Updates** — Auto-pull from GitHub on boot

## Quick Links

- [Installation Guide](getting-started/install.md)
- [Hardware Wiring](getting-started/hardware.md)
- [Architecture Overview](architecture/overview.md)
- [Creating Widgets](widgets/creating.md)
- [REST API Reference](web/api.md)
- [Voice Commands](voice.md)
- [Contributing](contributing.md)

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Display | pygame + kmsdrm (480x320 → HDMI) |
| OBD-II | bleak (BLE GATT) |
| Radar | pygatt/gatttool (BLE) |
| Audio | ALSA + bluealsa (BT A2DP) |
| Voice | Vosk (offline STT) |
| Web | Python HTTPServer (threaded) |
| Storage | SQLite (battery history) |
| Updates | Git clone + smart file sync |
