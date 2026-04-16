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
        # Disconnect any classic BT to OBD adapter (blocks BLE)
        try:
            import subprocess
            r = subprocess.run(["bluetoothctl", "devices", "Connected"],
                               capture_output=True, text=True, timeout=3)
            for line in r.stdout.splitlines():
                if any(x in line.lower() for x in OBD_NAMES):
                    mac = line.split()[1] if len(line.split()) > 1 else ""
                    if mac:
                        subprocess.run(["bluetoothctl", "disconnect", mac],
                                       capture_output=True, timeout=5)
                        log(f"Disconnected classic BT from OBD: {mac}")
                        await asyncio.sleep(2)
        except Exception:
            pass

        # First try saved address (skip scan entirely — much faster)
        saved = self._load_saved_addr()
        if saved:
            log(f"Trying saved OBD address: {saved}")
            try:
                async with BleakClient(saved, timeout=5) as test:
                    if test.is_connected:
                        log(f"Connected to saved adapter: {saved}")
                        return saved
            except Exception:
                log("Saved address failed, scanning...")

        # BLE scan
        log("Scanning BLE for OBD adapter...")
        devices = await BleakScanner.discover(timeout=10, return_adv=True)
        for addr, (dev, adv) in devices.items():
            name = (dev.name or "").lower()
            for obd_name in OBD_NAMES:
                if obd_name in name:
                    log(f"Found: {dev.name} ({addr}) RSSI={adv.rssi}")
                    self._save_addr(addr)
                    return addr

        # Last resort: check if adapter is paired via classic BT
        try:
            import subprocess
            r = subprocess.run(["bluetoothctl", "devices", "Paired"],
                               capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                for obd_name in OBD_NAMES:
                    if obd_name in line.lower():
                        mac = line.split()[1] if len(line.split()) > 1 else ""
                        if mac:
                            log(f"Found paired OBD: {mac}")
                            self._save_addr(mac)
                            return mac
        except Exception:
            pass

        return None

    def _load_saved_addr(self):
        try:
            with open("/home/chrismslist/car-hud/.obd_adapter") as f:
                return f.read().strip()
        except Exception:
            return None

    def _save_addr(self, addr):
        try:
            with open("/home/chrismslist/car-hud/.obd_adapter", "w") as f:
                f.write(addr)
        except Exception:
            pass

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
                # Signal other BLE services that OBD is using the radio
                try:
                    with open("/tmp/car-hud-obd-ble-lock", "w") as lf:
                        lf.write(str(time.time()))
                except Exception:
                    pass

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

                    # Main read loop — prioritize speed/RPM for instant response
                    data = {}
                    last_dtc_check = 0
                    cycle = 0

                    while client.is_connected:
                        warnings = []

                        # FAST group: RPM, Speed, Load, Throttle — EVERY cycle
                        fast_group = PID_GROUPS[0]
                        cmd = "".join(fast_group)
                        resp = await self.send(client, cmd, 3)
                        if "NO DATA" in resp or "ERROR" in resp or not resp:
                            for pid in fast_group:
                                resp = await self.send(client, pid, 2)
                                data.update(self.parse_group_response(resp, [pid]))
                        else:
                            data.update(self.parse_group_response(resp, fast_group))

                        # Write IMMEDIATELY after fast group — don't wait for slow
                        write_obd({
                            "connected": True,
                            "status": "connected",
                            "adapter": "Vgate iCar Pro 2S (BLE)",
                            "data": dict(data),
                            "warnings": warnings,
                            "dtcs": [],
                            "timestamp": time.time()
                        })

                        # SLOW group: Fuel, Battery, Temps — every 3rd cycle
                        if cycle % 3 == 0 and len(PID_GROUPS) > 1:
                            slow_group = PID_GROUPS[1]
                            cmd = "".join(slow_group)
                            resp = await self.send(client, cmd, 3)
                            if "NO DATA" in resp or "ERROR" in resp or not resp:
                                for pid in slow_group:
                                    resp = await self.send(client, pid, 2)
                                    data.update(self.parse_group_response(resp, [pid]))
                            else:
                                data.update(self.parse_group_response(resp, slow_group))

                        # Only warn on critical overheating
                        cool = data.get("COOLANT_TEMP", 0)
                        if cool > 110: warnings.append(f"OVERHEAT {cool:.0f}C")

                        # DTC check every 60s
                        dtcs = []
                        if time.time() - last_dtc_check > 60:
                            last_dtc_check = time.time()
                            resp = await self.send(client, "03", 5)
                            if resp and "43" in resp:
                                try:
                                    raw = "".join(resp.split()).upper()
                                    if len(raw) >= 6:
                                        dtcs.append(f"P{raw[2:6]}")
                                except Exception: pass

                        # Final write with all data + warnings + dtcs
                        write_obd({
                            "connected": True,
                            "status": "connected",
                            "adapter": "Vgate iCar Pro 2S (BLE)",
                            "data": dict(data),
                            "warnings": warnings,
                            "dtcs": dtcs,
                            "timestamp": time.time()
                        })

                        cycle += 1
                        await asyncio.sleep(0.05)  # 50ms between cycles = ~20Hz

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
