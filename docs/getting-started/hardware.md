# Hardware Setup

## GPIO Wiring

Orientation: USB/Ethernet ports facing you, GPIO header at far-left corner.

```
Pin1 ● 3.3V              ● Pin2  5V ← Lux VCC
Pin3 ● SDA  ← Lux SDA    ● Pin4
Pin5 ● SCL  ← Lux SCL    ● Pin6  GND ← Lux GND
Pin7 ●                    ● Pin8
Pin9 ●                    ● Pin10
Pin11●                    ● Pin12 GPIO18 ← Display PWM
Pin13●                    ● Pin14 GND   ← Display GND
```

## Display (TFT via HDMI + USB)

| Connection | Purpose |
|-----------|---------|
| HDMI | Video output (auto-scales 480x320 → display resolution) |
| USB | Touchscreen input (ChipOne HID) |
| PWM wire | Backlight brightness (GPIO 18, pin 12) |
| GND wire | Ground for PWM (pin 14) |

## OBD-II Adapter (Vgate iCar Pro 2S)

- Plugs into car's OBD-II port (under steering column)
- Connects via **BLE** (not classic Bluetooth)
- Pi auto-discovers on boot (`IOS-Vlink` device name)
- Must be powered from car's 12V (not USB)

## Cobra RAD 700i Radar Detector

- Connects via **BLE** (pygatt/gatttool backend)
- Only advertises for ~30 seconds after power-on
- Pi's Cobra service continuously scans and auto-connects
- GPS data shared with weather widget via `/tmp/car-hud-gps`

## BH1750 Lux Sensor (Optional)

- I2C address: `0x23` (default) or `0x5C` (ADDR→VCC)
- Needs **5V** on VCC (3.3V may not work for some modules)
- Enable in `display_service.py`: set `LUX_ENABLED = True`

## Audio

| Output | Device |
|--------|--------|
| Headphone jack | Card 0 (`hw:0,0`) — all audio output |
| USB soundcard | Card 1 — microphone input only |
| Bluetooth A2DP | Phone → Pi → headphone jack via bluealsa |
| Spotify Connect | Raspotify (librespot) → `plughw:0,0` |
