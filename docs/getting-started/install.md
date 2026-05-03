# Installation

## Requirements

- Raspberry Pi 3B+ (or later) with Pi OS Lite (64-bit)
- 2.5" TFT display (HDMI + USB touch)
- Vgate iCar Pro 2S (BLE OBD-II adapter)
- 64GB+ microSD card
- Internet connection (for initial setup)

## Clone & Setup

```bash
git clone https://github.com/grabercn/Car-HUD.git ~/car-hud
cd ~/car-hud

# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3-pygame python3-pil python3-pip \
    bluez bluealsa-utils ffmpeg v4l-utils libegl1 libgles2 \
    fonts-noto-cjk fonts-freefont-ttf ddcutil evtest

# Install Python packages
pip3 install --break-system-packages bleak spotipy pygatt pexpect

# Install services
sudo cp services/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable car-hud car-hud-obd car-hud-web car-hud-wifi \
    car-hud-spotify car-hud-touch car-hud-display car-hud-cobra \
    car-hud-battery bt-autoconnect

# Generate assets
python3 src/generate_splash.py
python3 src/generate_sounds.py
python3 src/generate_radar_sounds.py

# Start everything
sudo reboot
```

## OTA Updates

The system auto-updates from GitHub on boot via `update.sh`. To update manually:

```bash
sudo bash ~/car-hud/update.sh
```
