#!/bin/bash
# Car-HUD Installation Script
# Plug and play — handles everything automatically.
# Run on Raspberry Pi: sudo bash install.sh

set -e
INSTALL_DIR="/home/chrismslist/car-hud"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER="chrismslist"

echo "=== Car-HUD Installer ==="
echo "Installing from: $REPO_DIR"
echo "Target: $INSTALL_DIR"

# Create install directory
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/dashcam"

# Copy source files
cp "$REPO_DIR"/src/*.py "$INSTALL_DIR/"
cp "$REPO_DIR"/src/*.sh "$INSTALL_DIR/" 2>/dev/null || true
chown -R $USER:$USER "$INSTALL_DIR"
echo "Source files copied"

# ── System dependencies ──
echo "Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    python3-pygame python3-pillow python3-smbus python3-pyaudio python3-pip \
    fbi ffmpeg espeak libegl1 libegl-dev libgles2 patchelf fonts-liberation2 fonts-dejavu-core \
    portaudio19-dev git unzip avahi-daemon 2>&1 | tail -3

# ── Python dependencies ──
echo "Installing Python packages..."
pip3 install vosk obd bleak --break-system-packages 2>&1 | tail -3 || true

# Fix vosk library (executable stack issue on Pi)
find / -name "libvosk.so" -exec patchelf --clear-execstack {} \; 2>/dev/null || true
echo "Python packages done"

# ── Download Honda logo ──
if [ ! -f "$INSTALL_DIR/honda_logo.png" ]; then
    echo "Downloading Honda logo..."
    wget -q -O "$INSTALL_DIR/honda_logo.png" \
        'https://pngimg.com/uploads/honda/honda_PNG102932.png' 2>/dev/null || true
fi

# ── Generate sounds + splash ──
echo "Generating sounds..."
cd "$INSTALL_DIR"
python3 generate_sounds.py 2>/dev/null || true
echo "Generating splash..."
python3 generate_splash.py 2>/dev/null || true

# ── Download Vosk model ──
if [ ! -d "$INSTALL_DIR/vosk-model" ]; then
    echo "Downloading Vosk speech model..."
    cd "$INSTALL_DIR"
    wget -q https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip -O vosk.zip
    unzip -qo vosk.zip
    mv vosk-model-small-en-us-0.15 vosk-model
    rm vosk.zip
fi

# ── Install systemd services ──
echo "Installing services..."
for svc in "$REPO_DIR"/services/*.service; do
    cp "$svc" /etc/systemd/system/
done
systemctl daemon-reload

# Enable services
for svc in car-hud-splash car-hud car-hud-voice car-hud-obd \
           car-hud-wifi car-hud-dashcam car-hud-web; do
    systemctl enable "$svc" 2>/dev/null || true
done

# ── Boot optimizations ──
echo "Optimizing boot..."
# Disable unnecessary services
systemctl disable --now cloud-init cloud-init-local cloud-config cloud-final 2>/dev/null || true
apt-get purge -y -qq cloud-init cloud-guest-utils 2>/dev/null || true
systemctl disable --now ModemManager apparmor udisks2 systemd-pstore 2>/dev/null || true
systemctl disable --now fstrim.timer console-setup rpi-eeprom-update 2>/dev/null || true
systemctl disable --now e2scrub_reap.service e2scrub_all.timer 2>/dev/null || true
systemctl disable --now keyboard-setup.service triggerhappy.service 2>/dev/null || true
systemctl disable --now dphys-swapfile.service apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true
systemctl disable --now man-db.timer logrotate.timer 2>/dev/null || true
systemctl mask systemd-rfkill.service systemd-rfkill.socket 2>/dev/null || true
systemctl mask keyboard-setup.service e2scrub_reap.service triggerhappy.service 2>/dev/null || true

# Clean boot display
CMDLINE="console=serial0,115200 console=tty1 root=$(grep -o 'PARTUUID=[^ ]*' /boot/firmware/cmdline.txt) rootfstype=ext4 fsck.repair=yes rootwait quiet splash loglevel=0 logo.nologo vt.global_cursor_default=0 consoleblank=0"
echo "$CMDLINE" > /boot/firmware/cmdline.txt

# Force HDMI + SD overclock
grep -q hdmi_force_hotplug /boot/firmware/config.txt || echo "hdmi_force_hotplug=1" >> /boot/firmware/config.txt
grep -q sd_overclock /boot/firmware/config.txt || echo "dtparam=sd_overclock=100" >> /boot/firmware/config.txt
grep -q disable_splash /boot/firmware/config.txt || echo "disable_splash=1" >> /boot/firmware/config.txt

# Hide systemd status on boot
mkdir -p /etc/systemd/system.conf.d
echo -e "[Manager]\nShowStatus=no" > /etc/systemd/system.conf.d/hide-status.conf

# Mask getty on tty1 (HUD takes over)
systemctl mask getty@tty1 2>/dev/null || true

# ── SD card protection ──
grep -q "tmpfs /tmp" /etc/fstab || echo "tmpfs /tmp tmpfs defaults,noatime,nosuid,size=64M 0 0" >> /etc/fstab

# Journal to RAM
mkdir -p /etc/systemd/journald.conf.d
echo -e "[Journal]\nStorage=volatile\nRuntimeMaxUse=16M" > /etc/systemd/journald.conf.d/volatile.conf

# ── Network hardening ──
# WiFi watchdog
cat > /etc/systemd/system/nm-watchdog.service << 'EOF'
[Unit]
Description=NetworkManager WiFi Watchdog
After=NetworkManager.service

[Service]
Type=simple
ExecStart=/bin/bash -c "while true; do sleep 30; if ! nmcli -t -f STATE general 2>/dev/null | grep -q connected; then systemctl restart NetworkManager; sleep 10; fi; done"
Restart=always

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable nm-watchdog 2>/dev/null || true

# NM stability config
mkdir -p /etc/NetworkManager/conf.d
cat > /etc/NetworkManager/conf.d/stable.conf << 'EOF'
[main]
autoconnect-retries-default=5
[connection]
ipv4.dhcp-timeout=30
[device]
wifi.scan-rand-mac-address=no
wifi.powersave=2
EOF

# ── System config ──
hostnamectl set-hostname Car-HUD 2>/dev/null || true

# Auto-login
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf << EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin $USER --noclear %I \$TERM
EOF

# Sudoers for dashcam control
echo "$USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop car-hud-dashcam, /usr/bin/systemctl start car-hud-dashcam, /usr/bin/pkill" > /etc/sudoers.d/car-hud
chmod 440 /etc/sudoers.d/car-hud

# Helper command
cat > /usr/local/bin/car-hud << EOF
#!/bin/bash
sudo killall fbi 2>/dev/null
exec python3 $INSTALL_DIR/hud.py
EOF
chmod +x /usr/local/bin/car-hud

# API key placeholder
if [ ! -f "$INSTALL_DIR/.keys.json" ]; then
    echo '{"gemini":""}' > "$INSTALL_DIR/.keys.json"
    chown $USER:$USER "$INSTALL_DIR/.keys.json"
fi

# Fix ownership
chown -R $USER:$USER "$INSTALL_DIR"

echo ""
echo "=== Installation Complete ==="
echo "Reboot to start: sudo reboot"
echo "Web viewer: http://Car-HUD.local:8080"
