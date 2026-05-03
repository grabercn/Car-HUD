# Architecture Overview

Car-HUD uses a **multi-service architecture** where each feature runs as an independent systemd service. Services communicate via JSON files in `/tmp/`.

## Service Map

```
┌─────────────────────────────────────────────────┐
│                   car-hud                        │
│        Main display (pygame + kmsdrm)            │
│  Reads: all /tmp/car-hud-* files                 │
│  Renders: pages, widgets, overlays               │
└────────────┬────────────────────────┬────────────┘
             │ reads                  │ reads
    ┌────────┴────────┐     ┌────────┴────────┐
    │  car-hud-obd    │     │ car-hud-spotify  │
    │  OBD-II + Cobra │     │ Spotify Connect  │
    │  via BLE        │     │ + API polling    │
    └─────────────────┘     └─────────────────┘
    ┌─────────────────┐     ┌─────────────────┐
    │ car-hud-battery │     │  car-hud-web     │
    │ HV battery      │     │ Web UI + APIs    │
    │ health tracking │     │ port 8080        │
    └─────────────────┘     └─────────────────┘
    ┌─────────────────┐     ┌─────────────────┐
    │ car-hud-display │     │  car-hud-voice   │
    │ PWM brightness  │     │ Vosk STT         │
    │ GPIO 18         │     │ "Hey Honda"      │
    └─────────────────┘     └─────────────────┘
    ┌─────────────────┐     ┌─────────────────┐
    │  car-hud-wifi   │     │  car-hud-touch   │
    │ WiFi + tether   │     │ Touchscreen      │
    │ management      │     │ evdev → gestures │
    └─────────────────┘     └─────────────────┘
```

## Design Principles

1. **Crash isolation** — each service restarts independently
2. **File-based IPC** — JSON files in `/tmp/`, no sockets or pipes
3. **Auto-discovery** — widgets, cameras, BLE devices found automatically
4. **Zero config** — works out of the box, customize via web/voice
5. **Offline first** — everything works without internet (weather, recent tracks are optional)
