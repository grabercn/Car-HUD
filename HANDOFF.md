# Car-HUD Project — Complete Handoff Document
## As of 2026-04-13 evening

---

## 1. WHAT THIS IS

A Raspberry Pi 3B+ powered heads-up display for a 2014 Honda Accord Hybrid. Voice-controlled, OBD-II connected, with dashcam, themes, and AI assistant. GitHub: https://github.com/grabercn/Car-HUD

## 2. HARDWARE

| Component | Details |
|-----------|---------|
| Compute | Raspberry Pi 3B+ (1GB RAM, 64GB SD) |
| Display | HY84832C035L-HDMI 3.5" TFT, 480x320, 1000 nits (NOT YET PHYSICALLY CONNECTED — using headless mode with web viewer) |
| OBD-II | Vgate iCar Pro 2S BT5.2 — connects via BLE (not classic BT). BLE name: "IOS-Vlink", MAC: 41:42:86:9A:00:9C |
| Camera 1 | Logitech C925e webcam — dashcam + secondary mic, /dev/video0 |
| Camera 2 | NEW camera arriving — NOT YET INTEGRATED (see TODO) |
| Audio In | AB13X USB Audio adapter — primary lapel mic |
| Audio Out | AB13X USB Audio via dmix (simultaneous record+play) |
| SSH | chrismslist@Car-HUD.local or 172.20.10.2 (hotspot), password: boobear3 |

## 3. NETWORK CONFIG

- **Jimmy** (phone hotspot): priority 100, password 12345678 — ALWAYS connects first
- **TKE Guest WIFI**: priority 50, password TKEGuest321 — fallback
- WiFi managed by NetworkManager with autoconnect priorities
- PWR LED on Pi: on = WiFi connected, off = disconnected
- WiFi connect plays chime_wifi.wav

## 4. ALL FILES ON PI (~/northstar/)

### Python Services
| File | Service Name | Description |
|------|-------------|-------------|
| hud.py | northstar-hud | Main HUD display (pygame, 480x320, 6 themes) |
| bootsplash.py | northstar-splash | Animated Honda boot splash with self-calibrating progress bar |
| voice.py | car-hud-voice | Dual-mic Vosk STT, wake word "Hey Honda", Gemini NLU |
| brain.py | (imported by voice) | Gemini 3.0F/2.5F/2.0F fallback chain + local intent |
| intent.py | (imported by brain) | Local keyword intent matcher (offline fallback) |
| wordlearn.py | (imported by voice) | Word corrections, phrase learning, audio reinforcement |
| obd_ble.py | car-hud-obd | OBD-II via BLE (bleak library), reads 16 PIDs |
| wifi_service.py | car-hud-wifi | WiFi management, auto-connect, LED control |
| dashcam_service.py | car-hud-dashcam | Webcam recording, 5-min chunks, 2GB/50 clip max |
| music_service.py | car-hud-music | Bluetooth A2DP music metadata (DISABLED — no phone paired) |
| screenshot_server.py | car-hud-web | Web viewer on port 8080: MJPEG HUD stream, live camera, dashcam browser |
| calibrate.py | (on-demand) | Voice calibration tool — plays voice sample, tests gain levels |
| denoise.py | (imported by voice) | SpeexDSP noise suppression via ctypes (CURRENTLY DISABLED — was causing segfaults) |
| generate_splash.py | (one-time) | Generates the static Honda splash PNG |
| update.sh | car-hud-updater | OTA update from GitHub on boot (30s delay for network) |

### Data Files
| File | Purpose |
|------|---------|
| .theme | Current theme {"theme":"blue","auto":false} |
| .boot_times.json | Rolling boot time averages for splash calibration |
| .audio_params.json | Learned mic gain parameters |
| .voice_profile.json | User voice characteristics |
| .word_corrections.json | Vosk word correction learning |
| .response_cache.json | Gemini response cache (saves tokens) |
| .known_networks.json | Saved WiFi networks (managed by wifi_service) |
| .keys.json | API keys (Gemini) |
| .version | Current Git commit hash (for OTA updates) |
| honda_logo.png | Honda H badge + HONDA text (2126x1431 RGBA) |
| honda_h_badge.png | Cropped H badge only |
| vosk-model/ | Vosk small English model (68MB) |
| sherpa-onnx-streaming-zipformer-en-20M-2023-02-17/ | Sherpa-ONNX model (installed but NOT in use — Vosk is primary) |
| dashcam/ | Recording chunks (chunk_YYYYMMDD_HHMMSS.mp4) |
| chime_wake.wav, chime_ok.wav, chime_err.wav, chime_think.wav, chime_wifi.wav | Sound effects (stereo 48kHz) |
| voice_sample.wav | User's "Hey Honda" training sample at /tmp/voice_sample.wav |

## 5. OBD-II DETAILS

- Connects via BLE using bleak library (Pi's classic BT is too weak for the adapter)
- obd_ble.py sends raw ELM327 AT commands over BLE GATT characteristic
- GATT UUID: bef8d6c9-9c21-4c9e-b632-bd58c1009f9f (read/write/notify)
- Currently reads 16 PIDs: RPM, SPEED (km/h!), COOLANT_TEMP, ENGINE_LOAD, THROTTLE_POS, FUEL_LEVEL, HYBRID_BATTERY_REMAINING, CONTROL_MODULE_VOLTAGE, INTAKE_TEMP, ABSOLUTE_LOAD, TIMING_ADVANCE, MAF, BAROMETRIC_PRESSURE, CATALYST_TEMP_B1S1, SHORT_FUEL_TRIM, LONG_FUEL_TRIM
- SPEED comes in km/h from OBD — HUD converts to mph (* 0.621371)
- EV mode detection: RPM < 100 = electric drive
- The car supports 67 total PIDs (tested via laptop with python-obd library on COM3)
- Laptop OBD bridge script at scripts/obd_bridge.py (reads via classic BT serial, forwards to Pi via SSH)

## 6. VOICE SYSTEM

- **Wake word**: "Hey Honda" — uses phonetic matching, expanded set includes "hundred", "handle", "haunted", etc.
- **STT**: Vosk small-en-us-0.15 (68MB) — single recognizer with 3 alternatives
- **Dual mics**: Each in its own thread (MicReader class), picks loudest per frame
- **Gain**: Adaptive per-frame, learned params in .audio_params.json. Training showed optimal gain ~5x for USB mic, ~2x for webcam mic at room distance
- **Text accumulation**: After wake word, buffers 3 seconds of fragments before processing
- **NLU**: Gemini Flash chain (3.0F → 2.5F → 2.0F) when online, local intent.py offline
- **TTS**: espeak → ffmpeg (mono→stereo 48kHz) → plughw for USB audio card
- **Sound output**: Auto-detects USB card via dmix for simultaneous record+play
- **Chimes**: wake (detected), ok (command success), err (failed), think (processing), wifi (connected)

### Known Voice Issues
- Vosk small model has limited accuracy — "honda" often heard as "hundred", "handle", "haunted"
- The denoise.py SpeexDSP wrapper causes segfaults — DISABLED in voice.py
- Sherpa-ONNX installed (better model) but Vosk is primary because sherpa's 20M model was WORSE
- Larger sherpa model (full size) only has encoder, no decoder/joiner — can't use transducer mode
- Voice service sometimes crashes when USB audio adapter disconnects (auto-restarts)

## 7. HUD DESIGN

### Themes (6)
blue, red, green, amber, day (white bg), night (ultra-dim). Each theme defines: primary, primary_dim, accent, bg, panel, border, border_lite, text_bright, text_med, text_dim.

### Vehicle Page Layout (when OBD connected)
- Top strip: time | EV/GAS badge | voltage
- Left pillar: vertical fuel bar with % and estimated miles
- Right pillar: vertical HV battery bar with % and EV miles
- Center: big speed arc gauge with RPM as thin inner ring
- Power/Charge meter: horizontal bar, CHG←→PWR (Honda hybrid style)
- Data bars: coolant, RPM, load, throttle (all with labels + values)
- Range estimate: total miles (fuel + EV)
- Music strip at bottom (if playing via Bluetooth)

### System Page (no OBD)
- Big time display, system bars (CPU temp, memory), Honda logo

### Status Strip (bottom)
- Module indicators: AUD, OBD, MUS, NET (with SSID), CAM, LUX
- Colors: primary=active, AMBER=searching, RED=recording/error, dim=off
- Split mic level bar under AUD (left=USB mic, right=webcam mic)
- Keyboard shortcuts shown when keyboard detected

### Overlays
- Voice assistant (full screen, pulsing ring, live transcript)
- Camera view (live webcam feed, stops dashcam while viewing)
- Calibration progress
- Help/keys reference
- Terminal (Ctrl+T drops to bash)

## 8. WEB SERVER (port 8080)

- **/** — HUD MJPEG stream with keyboard shortcuts + nav bar
- **/camera** — Live camera MJPEG (stops dashcam, restarts on leave)
- **/dashcam** — Browse recordings with play/download
- **/dashcam/video/filename.mp4** — Stream/download a clip
- **/stream** — Raw HUD MJPEG
- **/camera/stream** — Raw camera MJPEG
- **/key/[cmd]** — Send keyboard command (camera, help, blue, red, etc.)
- **/status** — JSON API with all service data
- Nav bar cuts into HUD view — padding-top:24px added but may need more

## 9. WHAT IS NOT DONE (TODO)

### High Priority
1. **Dashboard UI overlap/condensing** — User says "tons of overlap, clean that up" and "make better use of entire space, it's so condensed". Need to spread elements out, reduce overlap, make it look polished for actual driving use.
2. **Dual camera support** — Second camera arriving. Need: auto-detect all webcams, dashcam_service records from both, web viewer shows both feeds, CAM indicator shows 1-cam vs 2-cam status (e.g., half-filled = 1 cam, full = 2 cams).
3. **Smooth gauge animations** — Currently gauges jump to new values. Need lerp/easing so arc gauges and bars animate smoothly between readings. User specifically asked for this for driving use.
4. **"Hey Honda" saying "..."** — Voice overlay sometimes shows "..." instead of recognized text. Need to fix the transcript display logic.
5. **Voice sounds timing** — User wants chime to play IMMEDIATELY on wake detection (currently slight delay). Also wants distinct sounds: timeout sound when nothing detected after wake, thinking sound while processing, success sound on command recognized.

### Medium Priority
6. **Calibration tool timing** — Plays voice sample once then tests all gains on that one recording. User wants it to play fresh for EACH gain test. Also the calibration UI on HUD needs work.
7. **Better Vosk accuracy** — Consider downloading vosk-model-en-us-0.22 (1.8GB) if enough RAM, or find a better small model. The small model garbles words badly.
8. **OBD2 Bluetooth classic fallback** — Pi's BT can find "IOS-Vlink" via classic scan but can't connect via rfcomm. Only BLE works. If BLE fails, there's no fallback.
9. **Music service** — Currently disabled. Needs phone pairing via Bluetooth A2DP. The music_service.py reads AVRCP metadata.
10. **Read-only filesystem** — For SD card protection on power loss (car ignition off). Never implemented.

### Low Priority
11. **TTS not always audible** — espeak → ffmpeg → aplay pipeline sometimes fails silently. gTTS (Google) works when online but needs internet.
12. **Light sensor (BH1750)** — I2C sensor for auto brightness/theme. Hardware not yet connected. LUX indicator always dim.
13. **Arducam IMX519** — 16MP CSI camera. dtoverlay=imx519 in config.txt but camera has I/O error reading chip ID. Cable needs reseating.
14. **Update GitHub repo** — Local files have changes not pushed. Always pull from Pi before pushing.

## 10. KEY TECHNICAL NOTES

- **ALSA card numbers change on reboot** — Code finds devices by name (e.g., "Audio", "C925e") not card number
- **HUD uses kmsdrm** when display connected, falls back to "dummy" driver when headless (for screenshot server)
- **OTA updater** checks GitHub on every boot (30s delay). Compares commit hash, downloads src/*.py, replaces, restarts services.
- **Pi has 512MB swap** at /swapfile (may or may not exist after reboot)
- **Sudoers** configured for chrismslist to stop/start dashcam without password
- **Boot optimizations**: cloud-init purged, ModemManager disabled, apparmor/bluetooth(re-enabled)/udisks2/fstrim/console-setup disabled, quiet splash, no cursor, no kernel logo
- **Boot time**: ~12 seconds splash, ~22s total
- **The local northstar_local/ folder** may have cross-platform patches that break Pi. ALWAYS pull from Pi first.

## 11. CONNECTION CHEAT SHEET

```bash
# SSH (on Jimmy hotspot)
ssh chrismslist@172.20.10.2

# SSH (on any network with mDNS)
ssh chrismslist@Car-HUD.local

# Web viewer
http://172.20.10.2:8080

# Reboot
ssh chrismslist@172.20.10.2 "sudo reboot"

# View all logs
ssh chrismslist@172.20.10.2 "for f in /tmp/car-hud-*.log; do echo === \$f ===; tail -5 \$f; done"

# Check all services
ssh chrismslist@172.20.10.2 "for svc in northstar-hud car-hud-voice car-hud-obd car-hud-wifi car-hud-web car-hud-dashcam; do printf '%s: %s\n' \$svc \$(systemctl is-active \$svc); done"
```
