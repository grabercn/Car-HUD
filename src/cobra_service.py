#!/usr/bin/env python3
"""Car-HUD Cobra RAD 700i — instant-connect on detection.
The RAD 700i only advertises BLE for ~30s after power-on.
This service continuously scans and connects the INSTANT it appears.
Runs as standalone service (not merged with OBD — needs scan access).
OBD service must be stopped briefly for the initial scan+connect,
then both BLE connections coexist.
"""

import os
import json
import time
import struct
import asyncio
from bleak import BleakScanner, BleakClient

SIGNAL_FILE = "/tmp/car-hud-cobra-data"
GPS_FILE = "/tmp/car-hud-gps"
LOG_FILE = "/tmp/car-hud-cobra.log"
SAVED_ADDR_FILE = "/home/chrismslist/car-hud/.cobra_adapter"

COBRA_NAMES = ["rad 700", "rad700", "cobra rad"]
ALERT_CHAR = "b5e22deb-31ee-42ab-be6a-9be0837aa344"
GPS_CHAR = "0000fe51-8e22-4541-9d4c-21edae82ed19"
BAND_MAP = {0x01:"X", 0x02:"K", 0x04:"Ka", 0x08:"Laser", 0x10:"Ka-POP", 0x20:"K-POP"}


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def write_data(data):
    data["timestamp"] = time.time()
    try:
        with open(SIGNAL_FILE, "w") as f:
            json.dump(data, f)
    except: pass

def write_gps(lat, lon, speed=0, heading=0):
    try:
        with open(GPS_FILE, "w") as f:
            json.dump({"lat":lat,"lon":lon,"speed":speed,"heading":heading,
                       "source":"cobra_rad700i","timestamp":time.time()}, f)
    except: pass


async def main():
    log("Cobra RAD 700i service — waiting for detector...")
    write_data({"connected": False, "status": "scanning"})

    cobra_device = None

    def on_detect(device, adv):
        nonlocal cobra_device
        name = (device.name or "").lower()
        if any(n in name for n in COBRA_NAMES) and not cobra_device:
            cobra_device = device
            log(f"DETECTED: {device.name} ({device.address})")

    # Phase 1: Continuous background scan until Cobra appears
    # OBD service may block scanning — we retry every 30s
    while not cobra_device:
        try:
            scanner = BleakScanner(detection_callback=on_detect)
            await scanner.start()
            # Wait up to 20s for detection
            for _ in range(40):
                if cobra_device:
                    break
                await asyncio.sleep(0.5)
            await scanner.stop()
        except Exception as e:
            log(f"Scan error: {e}")

        if not cobra_device:
            await asyncio.sleep(10)

    # Phase 2: Connect
    log("Connecting to Cobra...")
    try:
        with open(SAVED_ADDR_FILE, "w") as f:
            f.write(cobra_device.address)
    except: pass

    while True:
        try:
            client = BleakClient(cobra_device, timeout=15)
            await client.connect()

            if not client.is_connected:
                raise Exception("Connect returned but not connected")

            log("Cobra CONNECTED!")
            write_data({"connected": True, "status": "connected"})

            # Subscribe to notifications
            alert = None
            strength = 0
            gps_lat = gps_lon = gps_speed = gps_heading = 0

            def on_alert(sender, data):
                nonlocal alert, strength
                if len(data) >= 1:
                    band = BAND_MAP.get(data[0], "")
                    if band:
                        alert = band
                        strength = min(data[1] if len(data) > 1 else 0, 10)
                        log(f"ALERT: {band} str={strength}")
                    elif data[0] == 0:
                        alert = None
                        strength = 0

            def on_gps(sender, data):
                nonlocal gps_lat, gps_lon, gps_speed, gps_heading
                try:
                    if len(data) >= 12:
                        gps_lat = struct.unpack("<i", data[0:4])[0] / 1e7
                        gps_lon = struct.unpack("<i", data[4:8])[0] / 1e7
                        gps_speed = struct.unpack("<H", data[8:10])[0]
                        gps_heading = struct.unpack("<H", data[10:12])[0]
                    elif len(data) >= 6:
                        gps_lat = struct.unpack("<i", data[0:4])[0] / 1e6
                        gps_lon = struct.unpack("<h", data[4:6])[0] / 1e4
                    if gps_lat != 0:
                        write_gps(gps_lat, gps_lon, gps_speed, gps_heading)
                except: pass

            try:
                await client.start_notify(ALERT_CHAR, on_alert)
            except Exception as e:
                log(f"Alert notify: {e}")

            try:
                await client.start_notify(GPS_CHAR, on_gps)
            except Exception as e:
                log(f"GPS notify: {e}")

            # Main loop
            while client.is_connected:
                try:
                    raw = await client.read_gatt_char(ALERT_CHAR)
                    on_alert(None, raw)
                except: pass

                try:
                    raw = await client.read_gatt_char(GPS_CHAR)
                    on_gps(None, raw)
                except: pass

                write_data({
                    "connected": True, "status": "active",
                    "alert": alert, "alert_strength": strength,
                    "gps_lat": gps_lat, "gps_lon": gps_lon,
                    "gps_speed": gps_speed, "gps_heading": gps_heading,
                })
                await asyncio.sleep(0.5)

        except Exception as e:
            log(f"Error: {e}")
            write_data({"connected": False, "status": str(e)[:50]})

        # If disconnected, go back to scanning
        log("Disconnected — scanning again...")
        cobra_device = None
        while not cobra_device:
            try:
                scanner = BleakScanner(detection_callback=on_detect)
                await scanner.start()
                for _ in range(40):
                    if cobra_device: break
                    await asyncio.sleep(0.5)
                await scanner.stop()
            except: pass
            if not cobra_device:
                await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(main())
