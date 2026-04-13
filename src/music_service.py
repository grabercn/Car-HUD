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
PAIR_FILE = "/home/chrismslist/car-hud/.paired_phone"
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
    """Read AVRCP media metadata via D-Bus / dbus-send.
    More robust parsing for track, artist, album, duration, and position.
    """
    data = {"playing": False, "track": "Unknown", "artist": "Unknown", "album": "Unknown",
            "duration": 0, "progress": 0}

    try:
        # Get all managed objects and find the one with MediaPlayer1
        result = subprocess.run(
            ["dbus-send", "--system", "--print-reply", "--dest=org.bluez", "/",
             "org.freedesktop.DBus.ObjectManager.GetManagedObjects"],
            capture_output=True, text=True, timeout=3
        )
        
        if "org.bluez.MediaPlayer1" not in result.stdout:
            return data

        # We found a player. Now get its properties directly for better parsing.
        # First, find the player path (e.g., /org/bluez/hci0/dev_XX_XX_XX_XX_XX_XX/player0)
        player_path = None
        for line in result.stdout.split("\n"):
            if "/org/bluez/hci0/dev_" in line and "object path" in line:
                path = line.split('"')[1]
                if "player" in path:
                    player_path = path
                    break
        
        if not player_path:
            return data

        # Get properties of this specific player
        prop_res = subprocess.run(
            ["dbus-send", "--system", "--print-reply", "--dest=org.bluez", player_path,
             "org.freedesktop.DBus.Properties.GetAll", "string:org.bluez.MediaPlayer1"],
            capture_output=True, text=True, timeout=3
        )
        
        output = prop_res.stdout
        data["playing"] = '"playing"' in output or '"active"' in output

        # Helper to extract variant values from dbus-send output
        def get_val(key, out):
            lines = out.split("\n")
            for i, line in enumerate(lines):
                if f'string "{key}"' in line:
                    # Value is usually in the next few lines
                    for j in range(i+1, i+5):
                        if j < len(lines):
                            if 'string "' in lines[j]:
                                return lines[j].split('"')[1]
                            elif 'uint32' in lines[j] or 'int32' in lines[j]:
                                return int(lines[j].split()[-1])
            return None

        # Extract metadata dict
        data["track"] = get_val("Title", output) or "Unknown"
        data["artist"] = get_val("Artist", output) or "Unknown"
        data["album"] = get_val("Album", output) or "Unknown"
        data["duration"] = (get_val("Duration", output) or 0) / 1000.0
        data["progress"] = (get_val("Position", output) or 0) / 1000.0
        
    except Exception as e:
        log(f"Metadata error: {e}")

    return data


def media_control(cmd):
    """Send playback commands (play, pause, next, previous)."""
    # Find player path first
    try:
        result = subprocess.run(
            ["dbus-send", "--system", "--print-reply", "--dest=org.bluez", "/",
             "org.freedesktop.DBus.ObjectManager.GetManagedObjects"],
            capture_output=True, text=True, timeout=2
        )
        player_path = None
        for line in result.stdout.split("\n"):
            if "/org/bluez/hci0/dev_" in line and "object path" in line:
                path = line.split('"')[1]
                if "player" in path:
                    player_path = path
                    break
        
        if player_path:
            method = cmd.capitalize() # Play, Pause, Next, Previous
            subprocess.run([
                "dbus-send", "--system", "--print-reply", "--dest=org.bluez",
                player_path, f"org.bluez.MediaPlayer1.{method}"
            ], capture_output=True, timeout=2)
            log(f"Media control: {method}")
            return True
    except Exception as e:
        log(f"Media control error: {e}")
    return False


def check_voice_commands():
    """Check for phone pairing and media playback voice commands."""
    try:
        with open(VOICE_FILE) as f:
            data = json.load(f)
            if time.time() - data.get("time", 0) > 5:
                return None
            action = data.get("action", "")
            target = data.get("target", "")
            raw = data.get("raw", "").lower()

            # Pairing
            if "pair" in raw or "setup" in raw or "add" in raw:
                if "phone" in raw or "bluetooth" in raw:
                    return "pair"
            if "remove" in raw or "forget" in raw or "unpair" in raw:
                if "phone" in raw or "bluetooth" in raw:
                    return "unpair"
            
            # Playback controls
            if action == "music":
                if target in ["play", "pause", "next", "previous", "stop"]:
                    return f"media:{target}"
            
            # Natural language fallbacks
            if "next song" in raw or "skip" in raw: return "media:next"
            if "previous song" in raw or "go back" in raw: return "media:previous"
            if "pause music" in raw: return "media:pause"
            if "play music" in raw or "resume" in raw: return "media:play"

    except Exception:
        pass
    return None


def main():
    log("Music service starting...")
    # Set friendly name and discoverable
    bt_cmd("system-alias Honda-HUD")
    bt_cmd("power on")
    bt_cmd("pairable on")
    bt_cmd("discoverable on")
    
    # Class 0x200404: Audio/Video, Wearable Headset/Speaker
    # This helps phones recognize it as a media device
    try:
        subprocess.run(["hciconfig", "hci0", "class", "0x200404"], 
                       capture_output=True, timeout=2)
    except Exception: pass

    write_music_data({"playing": False, "paired": False})

    last_reconnect = 0
    while True:
        # Check voice commands for pairing and media control
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
        elif cmd and cmd.startswith("media:"):
            target = cmd.split(":")[1]
            media_control(target)
            time.sleep(0.5)

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

        if not connected and time.time() - last_reconnect > 30:
            last_reconnect = time.time()
            log(f"Attempting reconnection to {name}...")
            bt_cmd(f"trust {mac}")
            bt_cmd(f"connect {mac}")
            time.sleep(5)
            try:
                info = bt_cmd(f"info {mac}")
                connected = "Connected: yes" in info
            except Exception: pass

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
