#!/usr/bin/env python3
"""Car-HUD Cobra RAD 700i — uses pygatt/gatttool (bleak times out on GATT resolution).
Scans via bleak (fast), connects via pygatt (reliable).
"""

import os
import json
import time
import struct
import asyncio
import threading

SIGNAL_FILE = "/tmp/car-hud-cobra-data"
GPS_FILE = "/tmp/car-hud-gps"
LOG_FILE = "/tmp/car-hud-cobra.log"
SAVED_ADDR_FILE = "/home/chrismslist/car-hud/.cobra_adapter"

COBRA_NAMES = ["rad 700", "rad700", "cobra rad"]
# GATT handles (from gatttool --characteristics)
ALERT_HANDLE = 0x0024  # b5e22deb - alert data (read+notify)
GPS_HANDLE = 0x000e    # 0000fe51 - GPS data (read+notify)

BAND_MAP = {0x01:"X", 0x02:"K", 0x04:"Ka", 0x08:"Laser", 0x10:"Ka-POP", 0x20:"K-POP"}


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception: pass

def write_data(data):
    data["timestamp"] = time.time()
    try:
        with open(SIGNAL_FILE, "w") as f:
            json.dump(data, f)
    except Exception: pass

def write_gps(lat, lon, speed=0, heading=0):
    try:
        with open(GPS_FILE, "w") as f:
            json.dump({"lat":lat,"lon":lon,"speed":speed,"heading":heading,
                       "source":"cobra_rad700i","timestamp":time.time()}, f)
    except Exception: pass


def scan_for_cobra():
    """Use bleak for fast BLE scan (async), return address if found."""
    import asyncio
    from bleak import BleakScanner

    found = [None]

    async def _scan():
        devs = await BleakScanner.discover(timeout=10, return_adv=True)
        for addr, (dev, adv) in devs.items():
            name = (dev.name or "").lower()
            if any(n in name for n in COBRA_NAMES):
                log(f"Scan found: {dev.name} ({addr})")
                found[0] = addr
                try:
                    with open(SAVED_ADDR_FILE, "w") as f:
                        f.write(addr)
                except Exception: pass
                return

    try:
        asyncio.run(_scan())
    except Exception: pass
    return found[0]


def connect_and_read(addr):
    """Connect via pygatt/gatttool and read data continuously."""
    import pygatt

    adapter = pygatt.GATTToolBackend()
    adapter.start(reset_on_start=False)

    log(f"Connecting via gatttool: {addr}")
    device = None
    try:
        device = adapter.connect(addr, timeout=15, address_type=pygatt.BLEAddressType.public)
        log("CONNECTED!")
        write_data({"connected": True, "status": "connected"})

        alert = None
        strength = 0
        gps_lat = gps_lon = 0.0
        gps_speed = gps_heading = 0

        # Subscribe to alert notifications
        def on_alert(handle, value):
            nonlocal alert, strength
            if len(value) >= 1:
                band = BAND_MAP.get(value[0], "")
                if band:
                    prev_alert = alert
                    alert = band
                    strength = min(value[1] if len(value) > 1 else 0, 10)
                    log(f"ALERT: {band} str={strength}")
                    # Play alert sound on new detection
                    if band != prev_alert:
                        sound_map = {
                            "X": "radar_x.wav", "K": "radar_k.wav",
                            "Ka": "radar_ka.wav", "Laser": "radar_laser.wav",
                        }
                        snd = sound_map.get(band, "radar_alert.wav")
                        try:
                            import subprocess
                            subprocess.Popen(
                                ["aplay", "-D", "default", "-q",
                                 f"/home/chrismslist/car-hud/{snd}"],
                                stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                        except Exception: pass
                elif value[0] == 0:
                    if alert:
                        log("Alert cleared")
                    alert = None
                    strength = 0

        def on_gps(handle, value):
            nonlocal gps_lat, gps_lon, gps_speed, gps_heading
            try:
                if len(value) >= 12:
                    gps_lat = struct.unpack("<i", value[0:4])[0] / 1e7
                    gps_lon = struct.unpack("<i", value[4:8])[0] / 1e7
                    gps_speed = struct.unpack("<H", value[8:10])[0]
                    gps_heading = struct.unpack("<H", value[10:12])[0]
                elif len(value) >= 6:
                    gps_lat = struct.unpack("<i", value[0:4])[0] / 1e6
                    gps_lon = struct.unpack("<h", value[4:6])[0] / 1e4
                if gps_lat != 0:
                    write_gps(gps_lat, gps_lon, gps_speed, gps_heading)
            except Exception: pass

        # Subscribe using UUID strings (pygatt handles lookup)
        try:
            device.subscribe("b5e22deb-31ee-42ab-be6a-9be0837aa344", callback=on_alert)
            log("Subscribed to alert notifications")
        except Exception as e:
            log(f"Alert subscribe err: {e}")

        try:
            device.subscribe("0000fe51-8e22-4541-9d4c-21edae82ed19", callback=on_gps)
            log("Subscribed to GPS notifications")
        except Exception as e:
            log(f"GPS subscribe err: {e}")

        # Main read loop
        while True:
            try:
                raw = device.char_read("b5e22deb-31ee-42ab-be6a-9be0837aa344")
                on_alert(None, raw)
            except Exception as e:
                log(f"Alert read err: {e}")
                break

            try:
                raw = device.char_read("0000fe51-8e22-4541-9d4c-21edae82ed19")
                on_gps(None, raw)
            except Exception as e:
                log(f"GPS read err: {e}")

            write_data({
                "connected": True, "status": "active",
                "alert": alert, "alert_strength": strength,
                "alert_raw": raw.hex() if raw else "",
                "gps_lat": gps_lat, "gps_lon": gps_lon,
                "gps_speed": gps_speed, "gps_heading": gps_heading,
            })

            time.sleep(0.5)

    except Exception as e:
        log(f"Connection error: {e}")
        write_data({"connected": False, "status": str(e)[:50]})
    finally:
        if device:
            try: device.disconnect()
            except Exception: pass
        try: adapter.stop()
        except Exception: pass


def main():
    log("Cobra RAD 700i service starting (pygatt)...")
    write_data({"connected": False, "status": "starting"})

    while True:
        # Try saved address first
        addr = None
        try:
            with open(SAVED_ADDR_FILE) as f:
                addr = f.read().strip()
        except Exception: pass

        if not addr:
            log("Scanning for Cobra...")
            addr = scan_for_cobra()

        if addr:
            connect_and_read(addr)
        else:
            log("Cobra not found, retrying in 15s...")
            write_data({"connected": False, "status": "not found"})

        time.sleep(15)


if __name__ == "__main__":
    main()
