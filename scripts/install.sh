#!/bin/bash
# Car-HUD Installation Script
# Run on Raspberry Pi 3B+: sudo bash install.sh

set -e
INSTALL_DIR="/home/chrismslist/car-hud"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Car-HUD Installer ==="
echo "Installing from: $REPO_DIR"
echo "Target: $INSTALL_DIR"

# Create install directory
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/dashcam"

# Copy source files
cp "$REPO_DIR"/src/*.py "$INSTALL_DIR/"
echo "Source files copied"

# Install dependencies
apt-get update -qq
apt-get install -y -qq python3-pygame python3-pillow python3-smbus python3-pyaudio \
    fbi ffmpeg espeak patchelf fonts-liberation2 portaudio19-dev git unzip

# Generate sound files
python3 "$INSTALL_DIR/generate_sounds.py"
echo "Sound files generated"
pip3 install vosk obd bleak sherpa-onnx --break-system-packages 2>/dev/null || true

# Fix vosk if needed
patchelf --clear-execstack /home/chrismslist/.local/lib/python3.*/site-packages/vosk/libvosk.so 2>/dev/null || true

# Install systemd services
for svc in "$REPO_DIR"/services/*.service; do
    cp "$svc" /etc/systemd/system/
done
systemctl daemon-reload

# Enable services
for svc in car-hud-splash car-hud car-hud-voice car-hud-obd \
           car-hud-wifi car-hud-dashcam car-hud-web hide-cursor; do
    systemctl enable "$svc" 2>/dev/null || true
done

# Create helper commands
cat > /usr/local/bin/car-hud << 'EOF'
#!/bin/bash
sudo killall fbi 2>/dev/null
exec python3 /home/chrismslist/car-hud/hud.py
EOF
chmod +x /usr/local/bin/car-hud

# Download Vosk model if not present
if [ ! -d "$INSTALL_DIR/vosk-model" ]; then
    echo "Downloading Vosk speech model..."
    cd "$INSTALL_DIR"
    wget -q https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip -O vosk.zip
    unzip -qo vosk.zip
    mv vosk-model-small-en-us-0.15 vosk-model
    rm vosk.zip
fi

echo ""
echo "=== Installation Complete ==="
echo "Reboot to start: sudo reboot"
