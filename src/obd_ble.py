#!/usr/bin/env python3
"""OBD-II via Bluetooth LE — for Vgate iCar Pro 2S.
Connects via BLE, sends ELM327 commands, writes data to /tmp/car-hud-obd-data.
"""

import asyncio
import json
import time
import os
import sys
from bleak import BleakClient, BleakScanner

SIGNAL_FILE = "/tmp/car-hud-obd-data"
LOG_FILE = "/tmp/car-hud-obd.log"

# Vgate iCar Pro 2S BLE
OBD_NAMES = ["ios-vlink", "android-vlink", "vlink", "icar"]
CHAR_UUID = "bef8d6c9-9c21-4c9e-b632-bd58c1009f9f"  # read/write/notify

# PID configuration: (Name, parser_func, data_bytes)
PIDS = {
    "010C": ("RPM", lambda v: int(v, 16) / 4 if v else 0, 2),
    "010D": ("SPEED", lambda v: int(v, 16) if v else 0, 1),
    "0104": ("ENGINE_LOAD", lambda v: int(v, 16) * 100 / 255 if v else 0, 1),
    "0111": ("THROTTLE_POS", lambda v: int(v, 16) * 100 / 255 if v else 0, 1),
    "015B": ("HYBRID_BATTERY_REMAINING", lambda v: int(v, 16) * 100 / 255 if v else 0, 1),
    "012F": ("FUEL_LEVEL", lambda v: int(v, 16) * 100 / 255 if v else 0, 1),
    "0105": ("COOLANT_TEMP", lambda v: int(v, 16) - 40 if v else 0, 1),
    "0142": ("CONTROL_MODULE_VOLTAGE", lambda v: int(v, 16) / 1000 if v else 0, 2),
    "010F": ("INTAKE_TEMP", lambda v: int(v, 16) - 40 if v else 0, 1),
}

# Group PIDs into one command for speed (max 6 per command on most ELM327)
PID_GROUPS = [
    ["010C", "010D", "0104", "0111"], # Fast group (Engine/Speed)
    ["015B", "012F", "0105", "0142", "010F"] # Slower group (Levels/Temps)
]


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def write_obd(data):
    data["timestamp"] = time.time()
    try:
        with open(SIGNAL_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


class BleOBD:
    def __init__(self):
        self.response = ""
        self.response_ready = asyncio.Event()

    def on_notify(self, sender, data):
        text = data.decode("ascii", errors="ignore")
        self.response += text
        if ">" in text:
            self.response_ready.set()

    async def send(self, client, cmd, timeout=5):
        self.response = ""
        self.response_ready.clear()
        await client.write_gatt_char(CHAR_UUID, f"{cmd}\r".encode())
        try:
            await asyncio.wait_for(self.response_ready.wait(), timeout)
        except asyncio.TimeoutError:
            pass
        return self.response.replace(">", "").strip()

    async def find_adapter(self):
        log("Scanning BLE for OBD adapter...")
        devices = await BleakScanner.discover(timeout=10, return_adv=True)
        for addr, (dev, adv) in devices.items():
            name = (dev.name or "").lower()
            for obd_name in OBD_NAMES:
                if obd_name in name:
                    log(f"Found: {dev.name} ({addr}) RSSI={adv.rssi}")
                    return addr
        return None

    def parse_group_response(self, response, pids):
        """Parse multi-PID response: '41 0C 1A F8 0D 00' -> {'RPM': ..., 'SPEED': ...}"""
        results = {}
        # Clean response: remove spaces, newlines, and headers
        cleaned = "".join(response.replace("\r", " ").replace("\n", " ").split()).upper()
        
        # ELM327 usually echoes back '41 <PID> <DATA>' for each PID in group
        for pid in pids:
            pid_num = pid[2:]
            header = f"41{pid_num}"
            idx = cleaned.find(header)
            if idx >= 0:
                name, parser, n_bytes = PIDS[pid]
                data_start = idx + len(header)
                raw = cleaned[data_start : data_start + n_bytes * 2]
                if len(raw) == n_bytes * 2:
                    try:
                        results[name] = parser(raw)
                    except Exception:
                        pass
        return results

    async def run(self):
        write_obd({"connected": False, "status": "scanning", "data": {}, "warnings": [], "dtcs": []})

        while True:
            addr = await self.find_adapter()
            if not addr:
                write_obd({"connected": False, "status": "no adapter", "data": {}, "warnings": [], "dtcs": []})
                await asyncio.sleep(10)
                continue

            try:
                async with BleakClient(addr, timeout=15) as client:
                    if not client.is_connected:
                        continue

                    await client.start_notify(CHAR_UUID, self.on_notify)
                    log("BLE connected, initializing ELM327...")
                    write_obd({"connected": False, "status": "initializing", "data": {}, "warnings": [], "dtcs": []})

                    # Init ELM327
                    await self.send(client, "ATZ", 3)
                    await self.send(client, "ATE0")
                    await self.send(client, "ATL0")
                    await self.send(client, "ATS0")
                    await self.send(client, "ATH0")
                    await self.send(client, "ATAT1") # Adaptive timing ON
                    resp = await self.send(client, "ATSP0")  # auto protocol
                    log(f"Protocol: auto")

                    # Trigger protocol detection
                    resp = await self.send(client, "0100", 10)
                    log(f"Supported PIDs: {resp[:40]}")

                    if "UNABLE" in resp or "ERROR" in resp:
                        log("Protocol detection failed — car off?")
                        write_obd({"connected": False, "status": "car off?", "data": {}, "warnings": [], "dtcs": []})
                        await asyncio.sleep(10)
                        continue

                    log("ELM327 ready — reading data")
                    write_obd({"connected": True, "status": "connected", "adapter": "Vgate iCar Pro 2S (BLE)",
                               "data": {}, "warnings": [], "dtcs": []})

                    # Main read loop
                    data = {}
                    last_dtc_check = 0
                    
                    while client.is_connected:
                        warnings = []
                        
                        # Read PID groups
                        for group in PID_GROUPS:
                            cmd = "".join(group)
                            resp = await self.send(client, cmd, 3)
                            
                            if "NO DATA" in resp or "ERROR" in resp or not resp:
                                # Fallback to sequential if grouped fails
                                for pid in group:
                                    resp = await self.send(client, pid, 2)
                                    parsed = self.parse_group_response(resp, [pid])
                                    data.update(parsed)
                            else:
                                parsed = self.parse_group_response(resp, group)
                                data.update(parsed)

                        # Threshold checks
                        cool = data.get("COOLANT_TEMP", 0)
                        if cool > 105: warnings.append(f"HOT COOLANT {cool:.0f}C")
                        hv = data.get("HYBRID_BATTERY_REMAINING", 0)
                        if hv < 15: warnings.append(f"LOW HV BATT {hv:.0f}%")
                        volts = data.get("CONTROL_MODULE_VOLTAGE", 0)
                        if volts < 11.5: warnings.append(f"LOW VOLTS {volts:.1f}V")

                        # Periodic DTC check (every 60s)
                        dtcs = []
                        if time.time() - last_dtc_check > 60:
                            last_dtc_check = time.time()
                            resp = await self.send(client, "03", 5)
                            if resp and "43" in resp:
                                # 43 01 33 -> P0133
                                try:
                                    raw = "".join(resp.split()).upper()
                                    if len(raw) >= 6:
                                        code = raw[2:6]
                                        dtcs.append(f"P{code}")
                                except Exception: pass

                        write_obd({
                            "connected": True,
                            "status": "connected",
                            "adapter": "Vgate iCar Pro 2S (BLE)",
                            "data": data,
                            "warnings": warnings,
                            "dtcs": dtcs,
                            "timestamp": time.time()
                        })

                        await asyncio.sleep(0.1) # Fast loop

            except Exception as e:
                log(f"BLE error: {e}")
                write_obd({"connected": False, "status": "disconnected", "data": {}, "warnings": [], "dtcs": []})
                await asyncio.sleep(5)

            except Exception as e:
                log(f"BLE error: {e}")
                write_obd({"connected": False, "status": "disconnected", "data": {}, "warnings": [], "dtcs": []})
                await asyncio.sleep(5)


async def main():
    log("OBD-II BLE service starting...")
    obd = BleOBD()
    await obd.run()


if __name__ == "__main__":
    asyncio.run(main())
