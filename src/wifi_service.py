#!/usr/bin/env python3
"""Honda Accord WiFi Manager
Manages WiFi connections via voice commands and auto-connect.
Saves known networks and auto-connects on boot.
Writes status to /tmp/car-hud-wifi-data for HUD.
Reads voice commands from /tmp/car-hud-voice-signal.

Voice commands:
  "Hey Honda scan networks" — scan and show available networks
  "Hey Honda connect to [name]" — connect to a network
  "Hey Honda disconnect wifi" — disconnect
  "Hey Honda forget network" — forget current network
"""

import os
import sys
import json
import time
import subprocess

SIGNAL_FILE = "/tmp/car-hud-wifi-data"
VOICE_FILE = "/tmp/car-hud-voice-signal"
KNOWN_NETWORKS_FILE = "/home/chrismslist/car-hud/.known_networks.json"
LOG_FILE = "/tmp/car-hud-wifi.log"


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
        if os.path.getsize(LOG_FILE) > 30000:
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()[-50:]
            with open(LOG_FILE, "w") as f:
                f.writelines(lines)
    except Exception:
        pass


def write_status(data):
    data["timestamp"] = time.time()
    try:
        with open(SIGNAL_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass
    check_play_wifi_chime(data.get("state", ""))

    # Control Pi PWR LED — on=connected, off=disconnected
    try:
        state = data.get("state", "")
        led = "1" if state == "connected" else "0"
        with open("/sys/class/leds/PWR/brightness", "w") as f:
            f.write(led)
    except Exception:
        pass

_last_wifi_state = "disconnected"

def check_play_wifi_chime(state):
    global _last_wifi_state
    if state == "connected" and _last_wifi_state != "connected":
        try:
            subprocess.Popen(["aplay", "-D", "default",
                             "/home/chrismslist/car-hud/chime_wifi.wav"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    _last_wifi_state = state


def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return False, "", str(e)


def get_connection_state():
    """Get current WiFi connection status."""
    ok, out, _ = run_cmd(["nmcli", "-t", "-f", "STATE", "general"])
    if ok:
        state = out.strip()
        if "connected" in state and "disconnected" not in state:
            return "connected"
        elif "connecting" in state:
            return "connecting"
    return "disconnected"


def get_current_ssid():
    """Get the SSID we're currently connected to."""
    ok, out, _ = run_cmd(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"])
    if ok:
        for line in out.split("\n"):
            if line.startswith("yes:"):
                return line.split(":", 1)[1]
    return None


def get_signal_strength():
    """Get signal strength of current connection."""
    ssid = get_current_ssid()
    if not ssid:
        return 0
    ok, out, _ = run_cmd(["nmcli", "-t", "-f", "SSID,SIGNAL", "dev", "wifi", "list"])
    if ok:
        for line in out.split("\n"):
            parts = line.split(":")
            if len(parts) >= 2 and parts[0] == ssid:
                try:
                    return int(parts[1])
                except Exception:
                    pass
    return 0


def scan_networks():
    """Scan for available WiFi networks."""
    ok, out, _ = run_cmd(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY",
                           "dev", "wifi", "list", "--rescan", "yes"], timeout=15)
    networks = []
    seen = set()
    if ok:
        for line in out.split("\n"):
            parts = line.split(":")
            if len(parts) >= 2 and parts[0] and parts[0] not in seen:
                seen.add(parts[0])
                networks.append({
                    "ssid": parts[0],
                    "signal": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0,
                    "security": parts[2] if len(parts) > 2 else ""
                })
    networks.sort(key=lambda x: -x["signal"])
    return networks[:15]


def connect_to_network(ssid, password=None):
    """Connect to a WiFi network."""
    log(f"Connecting to '{ssid}'...")
    write_status({"state": "connecting", "ssid": ssid})

    # Check if we already have a saved connection for this SSID
    ok, out, _ = run_cmd(["nmcli", "-t", "-f", "NAME", "connection", "show"])
    if ok and ssid in out:
        # Known network — just activate
        ok, out, err = run_cmd(["nmcli", "connection", "up", ssid], timeout=30)
        if ok:
            log(f"Connected to '{ssid}' (saved)")
            save_known_network(ssid)
            return True
        log(f"Failed to activate saved '{ssid}': {err}")

    # New network
    cmd = ["nmcli", "dev", "wifi", "connect", ssid]
    if password:
        cmd += ["password", password]
    ok, out, err = run_cmd(cmd, timeout=30)
    if ok:
        log(f"Connected to '{ssid}'")
        save_known_network(ssid, password)
        return True
    log(f"Failed to connect to '{ssid}': {err}")
    return False


def disconnect_wifi():
    """Disconnect from current WiFi."""
    ssid = get_current_ssid()
    if ssid:
        run_cmd(["nmcli", "connection", "down", ssid])
        log(f"Disconnected from '{ssid}'")
    return True


def forget_network(ssid=None):
    """Forget a saved network."""
    if not ssid:
        ssid = get_current_ssid()
    if ssid:
        run_cmd(["nmcli", "connection", "delete", ssid])
        remove_known_network(ssid)
        log(f"Forgot network '{ssid}'")
    return True


def load_known_networks():
    try:
        with open(KNOWN_NETWORKS_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def save_known_network(ssid, password=None):
    networks = load_known_networks()
    # Update or add
    for n in networks:
        if n["ssid"] == ssid:
            if password:
                n["password"] = password
            n["last_connected"] = time.time()
            break
    else:
        entry = {"ssid": ssid, "last_connected": time.time()}
        if password:
            entry["password"] = password
        networks.append(entry)
    # Keep only latest 3, sorted newest first
    networks.sort(key=lambda x: -x.get("last_connected", 0))
    networks = networks[:3]
    try:
        with open(KNOWN_NETWORKS_FILE, "w") as f:
            json.dump(networks, f)
    except Exception:
        pass


def remove_known_network(ssid):
    networks = load_known_networks()
    networks = [n for n in networks if n["ssid"] != ssid]
    try:
        with open(KNOWN_NETWORKS_FILE, "w") as f:
            json.dump(networks, f)
    except Exception:
        pass


def auto_connect():
    """Try to connect to any known network on startup."""
    if get_connection_state() == "connected":
        return True

    known = load_known_networks()
    if not known:
        return False

    log("Auto-connect: scanning for known networks...")
    write_status({"state": "connecting", "ssid": "scanning..."})

    available = scan_networks()
    available_ssids = {n["ssid"] for n in available}

    # Try known networks in order of last connected
    known.sort(key=lambda x: -x.get("last_connected", 0))
    for net in known:
        if net["ssid"] in available_ssids:
            log(f"Auto-connect: trying '{net['ssid']}'...")
            write_status({"state": "connecting", "ssid": net["ssid"]})
            if connect_to_network(net["ssid"], net.get("password")):
                return True

    log("Auto-connect: no known networks available")
    return False


def check_voice_commands():
    """Check for WiFi-related voice commands."""
    try:
        with open(VOICE_FILE) as f:
            data = json.load(f)
            if time.time() - data.get("time", 0) > 5:
                return None, None
            action = data.get("action", "")
            target = data.get("target", "")
            raw = data.get("raw", "").lower()
            extra = data

            if action == "wifi":
                return target, extra
    except Exception:
        pass
    return None, None


def main():
    log("WiFi manager starting...")

    # Auto-connect on startup
    auto_connect()

    last_voice_check = 0
    last_status_update = 0

    while True:
        now = time.time()

        # Update status every 5 seconds
        if now - last_status_update > 5:
            last_status_update = now
            state = get_connection_state()
            ssid = get_current_ssid()
            signal = get_signal_strength() if state == "connected" else 0

            status = {
                "state": state,
                "ssid": ssid or "",
                "signal": signal,
            }

            # If disconnected, try auto-connect every 30 seconds
            if state == "disconnected":
                if int(now) % 30 < 6:
                    auto_connect()

            write_status(status)

        # Check voice commands every 2 seconds
        if now - last_voice_check > 2:
            last_voice_check = now
            cmd, extra = check_voice_commands()

            if cmd == "scan":
                log("Voice: scanning networks")
                networks = scan_networks()
                write_status({"state": get_connection_state(),
                              "ssid": get_current_ssid() or "",
                              "scan_results": networks})

            elif cmd == "connect":
                # Extract SSID from voice
                raw = extra.get("raw", "") if extra else ""
                words = raw.lower().split()
                ssid_guess = ""
                for i, w in enumerate(words):
                    if w == "to" and i + 1 < len(words):
                        ssid_guess = " ".join(words[i+1:])
                        break
                    elif w == "connect" and i + 1 < len(words):
                        ssid_guess = " ".join(words[i+1:])
                        break

                if ssid_guess:
                    # Fuzzy match against available networks
                    available = scan_networks()
                    best = None
                    for net in available:
                        if ssid_guess in net["ssid"].lower():
                            best = net["ssid"]
                            break
                    if best:
                        connect_to_network(best)
                    else:
                        log(f"No network matching '{ssid_guess}'")
                        write_status({"state": "failed",
                                      "error": f"No network: {ssid_guess}"})

            elif cmd == "disconnect":
                disconnect_wifi()

            elif cmd == "forget":
                forget_network()

        time.sleep(1)


if __name__ == "__main__":
    main()
