# Car-HUD

A Raspberry Pi-powered heads-up display for the 2014 Honda Accord Hybrid. Voice-controlled, theme-aware, with live vehicle data, dashcam, and AI assistant.

## Features

- **Visual Dashboard** — Arc gauges for speed/RPM, colored bars for fuel, hybrid battery, coolant, engine load
- **6 Color Themes** — Blue, Red, Green, Amber, Day, Night (auto day/night by clock)
- **Voice Control** — "Hey Honda" wake word with Vosk STT + Gemini NLU
- **OBD-II Integration** — Live vehicle data via Bluetooth (Vgate iCar Pro 2S)
- **Dashcam** — Continuous recording with 5-min chunks, auto-rotate
- **Dual Microphone** — USB lapel + webcam mic with SNR-weighted selection
- **Auto-Gain** — Adaptive per-frame gain with reinforcement learning
- **Music Display** — Bluetooth A2DP/AVRCP metadata from phone
- **WiFi Manager** — Voice-controlled network switching with auto-connect
- **OTA Updates** — Auto-checks GitHub on boot, full-screen update overlay
- **Web Viewer** — Live MJPEG stream at `http://Car-HUD.local:8080` with keyboard shortcuts
- **Boot Splash** — Animated Honda logo with self-calibrating progress bar

## Hardware

| Component | Model |
|-----------|-------|
| Compute | Raspberry Pi 3B+ (1GB RAM) |
| Display | HY84832C035L-HDMI (3.5" TFT, 480x320, 1000 nits) |
| OBD-II | Vgate iCar Pro 2S BT5.2 |
| Camera | Logitech C925e (dashcam + secondary mic) |
| Audio | AB13X USB Audio (lapel mic + speaker) |
| Storage | 64GB SanDisk Ultra |

## Quick Start

```bash
# Clone to Pi
git clone https://github.com/grabercn/Car-HUD.git
cd Car-HUD

# Install
sudo bash scripts/install.sh

# Reboot
sudo reboot
```

## File Structure

```
src/
  hud.py              # Main HUD display (pygame, 480x320)
  voice.py            # Voice system (dual mic, Vosk STT, wake word)
  brain.py            # AI command processing (Gemini + local intent)
  intent.py           # Local intent matcher (offline fallback)
  wordlearn.py        # Word correction + audio reinforcement learning
  denoise.py          # SpeexDSP noise suppression (ctypes wrapper)
  obd_service.py      # OBD-II Bluetooth vehicle data monitor
  music_service.py    # Bluetooth A2DP music metadata
  wifi_service.py     # WiFi manager with auto-connect
  dashcam_service.py  # Webcam recording in 5-min chunks
  web_service.py # Web viewer (MJPEG stream + keyboard shortcuts)
  splash_service.py       # Animated Honda boot splash
  calibrate.py        # Voice calibration tool
  generate_splash.py  # Static splash image generator

services/             # systemd service files
scripts/
  install.sh          # Full installation script
  update.sh           # OTA update from GitHub
```

## Voice Commands

| Command | Action |
|---------|--------|
| "Hey Honda what's the weather" | AI response |
| "Hey Honda color red/blue/green/amber" | Change theme |
| "Hey Honda night mode / day mode" | Switch theme |
| "Hey Honda show camera" | Live camera view |
| "Hey Honda calibrate" | Run voice calibration |
| "Hey Honda scan networks" | WiFi scan |
| "Hey Honda connect to [network]" | WiFi connect |

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| C | Camera view |
| H | Help overlay |
| 1-6 | Themes (blue/red/green/amber/day/night) |
| F1 | Voice calibration |
| ? | Keyboard shortcuts |
| ESC | Close overlay |
| Ctrl+T | Terminal |
| Ctrl+Q | Quit |

## Web Viewer

Access from any device on the same network:
```
http://Car-HUD.local:8080
```
Supports keyboard shortcuts from the browser.

## Services

| Service | Description |
|---------|-------------|
| car-hud-splash | Boot splash with progress bar |
| car-hud | Main display |
| car-hud-voice | Voice recognition + commands |
| car-hud-obd | OBD-II vehicle data |
| car-hud-wifi | WiFi management |
| car-hud-dashcam | Dashcam recording |
| car-hud-web | Screenshot server |
| car-hud-updater | OTA update checker |

## License

MIT
