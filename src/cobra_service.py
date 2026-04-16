#!/usr/bin/env python3
"""Car-HUD Cobra RAD 700i Radar Detector Service
Pi 3B+ can't scan BLE while OBD is connected, so this service:
1. Waits for OBD to disconnect briefly (between reconnects)
2. Connects to Cobra using saved address
3. Stays connected alongside OBD (multi-connection works once both are connected)

GPS data written to /tmp/car-hud-gps for weather, maps, etc.
"""

import os
import sys
import json
import time
import struct
import asyncio

from bleak import BleakClient

SIGNAL_FILE = "/tmp/car-hud-cobra-data"
GPS_FILE = "/tmp/car-hud-gps"
LOG_FILE = "/tmp/car-hud-cobra.log"

SAVED_ADDR_FILE = "/home/chrismslist/car-hud/.cobra_adapter"

ALERT_CHAR = "b5e22deb-31ee-42ab-be6a-9be0837aa344"
GPS_CHAR = "0000fe51-8e22-4541-9d4c-21edae82ed19"

BAND_MAP = {
    0x01: "X", 0x02: "K", 0x04: "Ka", 0x08: "Laser",
    0x10: "Ka-POP", 0x20: "K-POP",
}


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def write_data(data):
    data["timestamp"] = time.time()
    try:
        with open(SIGNAL_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def write_gps(lat, lon, speed=0, heading=0):
    try:
        with open(GPS_FILE, "w") as f:
            json.dump({"lat": lat, "lon": lon, "speed": speed,
                        "heading": heading, "source": "cobra_rad700i",
                        "timestamp": time.time()}, f)
    except Exception:
        pass


class CobraDetector:
    def __init__(self):
        self.current_alert = None
        self.alert_strength = 0
        self.gps_lat = 0.0
        self.gps_lon = 0.0
        self.gps_speed = 0
        self.gps_heading = 0

    def on_alert(self, sender, data):
        if len(data) >= 1:
            band = BAND_MAP.get(data[0], "")
            strength = data[1] if len(data) > 1 else 0
            if band:
                self.current_alert = band
                self.alert_strength = min(strength, 10)
                log(f"ALERT: {band} str={strength}")
            elif data[0] == 0:
                if self.current_alert:
                    log("Alert cleared")
                self.current_alert = None
                self.alert_strength = 0

    def on_gps(self, sender, data):
        if len(data) >= 6:
            try:
                if len(data) >= 12:
                    self.gps_lat = struct.unpack("<i", data[0:4])[0] / 1e7
                    self.gps_lon = struct.unpack("<i", data[4:8])[0] / 1e7
                    self.gps_speed = struct.unpack("<H", data[8:10])[0] if len(data) >= 10 else 0
                    self.gps_heading = struct.unpack("<H", data[10:12])[0] if len(data) >= 12 else 0
                else:
                    self.gps_lat = struct.unpack("<i", data[0:4])[0] / 1e6
                    self.gps_lon = struct.unpack("<h", data[4:6])[0] / 1e4
                if self.gps_lat != 0:
                    write_gps(self.gps_lat, self.gps_lon, self.gps_speed, self.gps_heading)
            except Exception:
                pass

    async def run(self):
        write_data({"connected": False, "status": "starting"})

        addr = None
        try:
            with open(SAVED_ADDR_FILE) as f:
                addr = f.read().strip()
        except Exception:
            pass

        if not addr:
            log("No saved Cobra address — set .cobra_adapter file")
            write_data({"connected": False, "status": "no address"})
            # Wait and retry — maybe OBD service will release BLE for a scan
            while not addr:
                await asyncio.sleep(30)
                try:
                    with open(SAVED_ADDR_FILE) as f:
                        addr = f.read().strip()
                except Exception:
                    pass

        while True:
            log(f"Connecting to Cobra: {addr}")
            try:
                client = BleakClient(addr, timeout=10)
                await client.connect()

                if not client.is_connected:
                    raise Exception("Connection failed")

                log("Cobra connected!")
                write_data({"connected": True, "status": "connected"})

                try:
                    await client.start_notify(ALERT_CHAR, self.on_alert)
                except Exception as e:
                    log(f"Alert notify: {e}")

                try:
                    await client.start_notify(GPS_CHAR, self.on_gps)
                except Exception as e:
                    log(f"GPS notify: {e}")

                while client.is_connected:
                    # Read current values
                    try:
                        raw = await client.read_gatt_char(ALERT_CHAR)
                        self.on_alert(None, raw)
                    except Exception:
                        pass

                    try:
                        raw = await client.read_gatt_char(GPS_CHAR)
                        self.on_gps(None, raw)
                    except Exception:
                        pass

                    write_data({
                        "connected": True,
                        "status": "active",
                        "alert": self.current_alert,
                        "alert_strength": self.alert_strength,
                        "gps_lat": self.gps_lat,
                        "gps_lon": self.gps_lon,
                        "gps_speed": self.gps_speed,
                        "gps_heading": self.gps_heading,
                    })

                    await asyncio.sleep(0.5)

            except Exception as e:
                log(f"Error: {e}")
                write_data({"connected": False, "status": str(e)[:50]})

            await asyncio.sleep(10)


async def main():
    log("Cobra RAD 700i service starting...")
    # Wait 10s for OBD to connect first (OBD has priority)
    await asyncio.sleep(10)
    detector = CobraDetector()
    await detector.run()


if __name__ == "__main__":
    asyncio.run(main())
