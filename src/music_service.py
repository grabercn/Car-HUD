#!/usr/bin/env python3
"""Honda Accord Bluetooth Music Service
Connects to paired phone via Bluetooth A2DP/AVRCP.
Reads track metadata (artist, track, album, progress) without internet.
Also handles phone pairing/unpairing via voice commands.

Writes music data to /tmp/car-hud-music-data for HUD.
Reads voice commands from /tmp/car-hud-voice-signal for pairing.
"""

import os
import sys
import json
import time
import subprocess

SIGNAL_FILE = "/tmp/car-hud-music-data"
VOICE_FILE = "/tmp/car-hud-voice-signal"
PAIR_FILE = "/home/chrismslist/northstar/.paired_phone"
LOG_FILE = "/tmp/car-hud-music.log"


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
        if os.path.getsize(LOG_FILE) > 50000:
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()[-100:]
            with open(LOG_FILE, "w") as f:
                f.writelines(lines)
    except Exception:
        pass


def write_music_data(data):
    data["timestamp"] = time.time()
    try:
        with open(SIGNAL_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def bt_cmd(cmd):
    """Run a bluetoothctl command."""
    try:
        result = subprocess.run(
            ["bluetoothctl"] + cmd.split(),
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception as e:
        log(f"BT cmd error: {e}")
        return ""


def get_paired_phone():
    """Get saved paired phone MAC."""
    try:
        with open(PAIR_FILE) as f:
            data = json.load(f)
            return data.get("mac"), data.get("name")
    except Exception:
        return None, None


def save_paired_phone(mac, name):
    try:
        with open(PAIR_FILE, "w") as f:
            json.dump({"mac": mac, "name": name}, f)
        log(f"Saved paired phone: {name} ({mac})")
    except Exception:
        pass


def remove_paired_phone():
    mac, name = get_paired_phone()
    if mac:
        bt_cmd(f"disconnect {mac}")
        bt_cmd(f"remove {mac}")
        log(f"Removed phone: {name} ({mac})")
    try:
        os.remove(PAIR_FILE)
    except Exception:
        pass


def start_pairing():
    """Put Pi in discoverable/pairable mode for 60 seconds."""
    log("Starting phone pairing mode...")
    bt_cmd("discoverable on")
    bt_cmd("pairable on")
    bt_cmd("agent on")
    bt_cmd("default-agent")

    # Scan for devices
    subprocess.Popen(["bluetoothctl", "scan", "on"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    write_music_data({"playing": False, "pairing": True,
                      "pairing_status": "Waiting for phone..."})

    # Wait up to 60 seconds for a new device to pair
    start = time.time()
    while time.time() - start < 60:
        time.sleep(3)
        # Check for new paired devices
        output = bt_cmd("paired-devices")
        for line in output.split("\n"):
            if line.startswith("Device"):
                parts = line.split(" ", 2)
                if len(parts) >= 3:
                    mac = parts[1]
                    name = parts[2]
                    old_mac, _ = get_paired_phone()
                    if mac != old_mac:
                        # New device paired!
                        save_paired_phone(mac, name)
                        bt_cmd(f"trust {mac}")
                        bt_cmd("discoverable off")
                        bt_cmd("scan off")
                        write_music_data({"playing": False, "pairing": False,
                                          "paired": True, "phone": name})
                        log(f"Paired with: {name}")
                        return True

        write_music_data({"playing": False, "pairing": True,
                          "pairing_status": f"Searching... {60 - int(time.time() - start)}s"})

    bt_cmd("discoverable off")
    bt_cmd("scan off")
    write_music_data({"playing": False, "pairing": False})
    log("Pairing timeout")
    return False


def get_media_metadata():
    """Read AVRCP media metadata via D-Bus / bluetoothctl."""
    data = {"playing": False}

    try:
        # Use bluetoothctl to get media player info
        result = subprocess.run(
            ["dbus-send", "--system", "--print-reply",
             "--dest=org.bluez", "/",
             "org.freedesktop.DBus.ObjectManager.GetManagedObjects"],
            capture_output=True, text=True, timeout=5
        )
        output = result.stdout

        # Parse for MediaPlayer1 properties
        if "org.bluez.MediaPlayer1" in output:
            data["playing"] = True

            # Extract track info from dbus output
            lines = output.split("\n")
            for i, line in enumerate(lines):
                if "Title" in line and i + 1 < len(lines):
                    val = lines[i + 1].strip().strip('"')
                    if val and "variant" not in val:
                        data["track"] = val
                elif "Artist" in line and i + 1 < len(lines):
                    val = lines[i + 1].strip().strip('"')
                    if val and "variant" not in val:
                        data["artist"] = val
                elif "Album" in line and i + 1 < len(lines):
                    val = lines[i + 1].strip().strip('"')
                    if val and "variant" not in val:
                        data["album"] = val
                elif "Duration" in line and i + 1 < len(lines):
                    try:
                        val = int(lines[i + 1].strip().split()[-1])
                        data["duration"] = val / 1000  # ms to sec
                    except Exception:
                        pass
                elif "Position" in line and i + 1 < len(lines):
                    try:
                        val = int(lines[i + 1].strip().split()[-1])
                        data["progress"] = val / 1000
                    except Exception:
                        pass
    except Exception:
        pass

    return data


def check_voice_commands():
    """Check for phone pairing voice commands."""
    try:
        with open(VOICE_FILE) as f:
            data = json.load(f)
            if time.time() - data.get("time", 0) > 5:
                return None
            action = data.get("action", "")
            target = data.get("target", "")
            raw = data.get("raw", "").lower()

            # Check for pairing commands
            if "pair" in raw or "setup" in raw or "add" in raw:
                if "phone" in raw or "bluetooth" in raw:
                    return "pair"
            if "remove" in raw or "forget" in raw or "unpair" in raw:
                if "phone" in raw or "bluetooth" in raw:
                    return "unpair"
    except Exception:
        pass
    return None


def main():
    log("Music service starting...")

    write_music_data({"playing": False, "paired": False})

    while True:
        # Check voice commands for pairing
        cmd = check_voice_commands()
        if cmd == "pair":
            start_pairing()
            continue
        elif cmd == "unpair":
            remove_paired_phone()
            write_music_data({"playing": False, "paired": False,
                              "status": "Phone removed"})
            time.sleep(5)
            continue

        # Check if we have a paired phone
        mac, name = get_paired_phone()

        if not mac:
            write_music_data({"playing": False, "paired": False,
                              "status": "No phone paired"})
            time.sleep(5)
            continue

        # Try to connect to paired phone
        connected = False
        try:
            info = bt_cmd(f"info {mac}")
            connected = "Connected: yes" in info
        except Exception:
            pass

        if not connected:
            bt_cmd(f"connect {mac}")
            time.sleep(3)
            try:
                info = bt_cmd(f"info {mac}")
                connected = "Connected: yes" in info
            except Exception:
                pass

        if connected:
            # Read media metadata
            media = get_media_metadata()
            media["paired"] = True
            media["phone"] = name
            write_music_data(media)
        else:
            write_music_data({"playing": False, "paired": True,
                              "phone": name, "status": "Connecting..."})

        time.sleep(2)


if __name__ == "__main__":
    main()
