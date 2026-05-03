#!/usr/bin/env python3
"""Deep OBD-II PID probe — finds ALL available data from every ECU.
Stops the OBD service, probes all headers and PIDs, saves results.
Run: python3 obd_probe.py
"""

import asyncio
import json
import time
import os
from bleak import BleakScanner, BleakClient

CHAR = "bef8d6c9-9c21-4c9e-b632-bd58c1009f9f"
RESULTS_FILE = "/home/chrismslist/car-hud/obd_probe_results.json"
LOG_FILE = "/tmp/obd_probe.log"

resp = ""
rdy = asyncio.Event()
results = {"pids": {}, "headers": {}, "mode21": {}, "mode22": {}, "raw": []}


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def on_notify(sender, data):
    global resp
    resp += data.decode("ascii", errors="replace")
    if ">" in resp:
        rdy.set()


async def send(client, cmd, timeout=3):
    global resp
    resp = ""
    rdy.clear()
    await client.write_gatt_char(CHAR, f"{cmd}\r".encode())
    try:
        await asyncio.wait_for(rdy.wait(), timeout)
    except asyncio.TimeoutError:
        pass
    return resp.replace(">", "").strip()


async def probe():
    # Stop OBD service
    os.system("sudo systemctl stop car-hud-obd 2>/dev/null")
    os.system("bluetoothctl disconnect 41:42:86:9A:00:9C 2>/dev/null")
    await asyncio.sleep(2)

    log("Scanning for OBD adapter...")
    devs = await BleakScanner.discover(timeout=8, return_adv=True)
    obd_dev = None
    for addr, (dev, adv) in devs.items():
        if dev.name and "vlink" in dev.name.lower():
            obd_dev = dev
            log(f"Found: {dev.name} ({addr})")
            break

    if not obd_dev:
        log("OBD adapter NOT FOUND — is car ignition ON?")
        os.system("sudo systemctl start car-hud-obd 2>/dev/null")
        return

    async with BleakClient(obd_dev, timeout=15) as client:
        await client.start_notify(CHAR, on_notify)

        # Initialize ELM327
        log("Initializing ELM327...")
        await send(client, "ATZ", 3)
        await send(client, "ATE0")
        await send(client, "ATL0")
        await send(client, "ATS0")
        await send(client, "ATH1")  # Headers ON
        await send(client, "ATAT1")
        await send(client, "ATSP0")
        r = await send(client, "0100", 8)
        log(f"Protocol init: {r}")

        if "UNABLE" in r or "ERROR" in r:
            log("Car ECU not responding — is ignition in RUN position?")
            os.system("sudo systemctl start car-hud-obd 2>/dev/null")
            return

        # Phase 1: Supported PID ranges
        log("\n=== PHASE 1: Supported PID ranges ===")
        for base in ["0100", "0120", "0140", "0160", "0180", "01A0", "01C0"]:
            r = await send(client, base, 3)
            clean = r.replace(" ", "").replace("\r", "").replace("\n", "")
            if "NODATA" not in clean.upper() and len(clean) > 6:
                log(f"  {base}: {r}")
                results["pids"][base] = r

        # Phase 2: Every standard PID 01-7F
        log("\n=== PHASE 2: All Mode 01 PIDs ===")
        for pid_num in range(0x00, 0x80):
            pid = f"01{pid_num:02X}"
            r = await send(client, pid, 2)
            clean = r.replace(" ", "").replace("\r", "").replace("\n", "")
            if "NODATA" not in clean.upper() and "ERROR" not in clean.upper() and "?" not in clean and len(clean) > 4:
                log(f"  {pid}: {r}")
                results["pids"][pid] = r

        # Phase 3: Try ALL ECU headers with key PIDs
        log("\n=== PHASE 3: ECU Header scan ===")
        headers_to_try = [
            "7E0", "7E1", "7E2", "7E3", "7E4", "7E5", "7E6", "7E7",
            "7DF",  # broadcast
            "18DA10F1", "18DA11F1", "18DA17F1", "18DA1AF1",
            "18DA1EF1", "18DA28F1", "18DA33F1", "18DAF110",
        ]
        key_pids = [
            ("015B", "HV Battery SOC"),
            ("012F", "Fuel Level"),
            ("0105", "Coolant Temp"),
            ("0142", "Ctrl Module Voltage"),
            ("010F", "Intake Temp"),
            ("0146", "Ambient Temp"),
            ("015C", "Oil Temp"),
            ("015E", "Fuel Rate"),
            ("0151", "Fuel Type"),
            ("0149", "Accel Pedal D"),
            ("014A", "Accel Pedal E"),
            ("0104", "Engine Load"),
            ("010C", "RPM"),
        ]

        for hdr in headers_to_try:
            await send(client, f"ATSH{hdr}")
            found = []
            for pid, name in key_pids:
                r = await send(client, pid, 2)
                clean = r.replace(" ", "").replace("\r", "").replace("\n", "")
                if "NODATA" not in clean.upper() and "ERROR" not in clean.upper() and len(clean) > 4:
                    found.append((pid, name, r))
            if found:
                log(f"\n  Header {hdr} — {len(found)} PIDs respond:")
                results["headers"][hdr] = {}
                for pid, name, r in found:
                    log(f"    {pid} ({name}): {r}")
                    results["headers"][hdr][pid] = {"name": name, "raw": r}

        # Phase 4: Mode 21 with different headers
        log("\n=== PHASE 4: Mode 21 (Honda Manufacturer) ===")
        for hdr in ["7E0", "7E2", "7E4", "7DF"]:
            await send(client, f"ATSH{hdr}")
            for pid_num in range(0x01, 0x60):
                pid = f"21{pid_num:02X}"
                r = await send(client, pid, 2)
                clean = r.replace(" ", "").replace("\r", "").replace("\n", "")
                if "NODATA" not in clean.upper() and "?" not in clean and "ERROR" not in clean.upper() and len(clean) > 4:
                    key = f"{hdr}/{pid}"
                    log(f"  [{hdr}] {pid}: {r}")
                    results["mode21"][key] = r

        # Phase 5: Mode 22 with different headers
        log("\n=== PHASE 5: Mode 22 (Extended Diagnostics) ===")
        for hdr in ["7E0", "7E2", "7E4"]:
            await send(client, f"ATSH{hdr}")
            for hi in [0x00, 0x01, 0x02, 0x10, 0x11, 0x20, 0x21, 0x22,
                       0x30, 0x31, 0x40, 0x41, 0x50, 0x60, 0x70, 0xF0, 0xF1, 0xF2]:
                for lo in range(0x00, 0x20):
                    pid = f"22{hi:02X}{lo:02X}"
                    r = await send(client, pid, 1)
                    clean = r.replace(" ", "").replace("\r", "").replace("\n", "")
                    if "NODATA" not in clean.upper() and "?" not in clean and "ERROR" not in clean.upper() and len(clean) > 6:
                        key = f"{hdr}/{pid}"
                        log(f"  [{hdr}] {pid}: {r}")
                        results["mode22"][key] = r

        # Phase 6: Mode 09 (Vehicle info)
        log("\n=== PHASE 6: Mode 09 (Vehicle Info) ===")
        await send(client, "ATSH7DF")
        for pid_num in range(0x00, 0x0F):
            pid = f"09{pid_num:02X}"
            r = await send(client, pid, 3)
            clean = r.replace(" ", "").replace("\r", "").replace("\n", "")
            if "NODATA" not in clean.upper() and len(clean) > 4:
                log(f"  {pid}: {r}")
                results["pids"][pid] = r

        # Reset ELM327 to defaults
        await send(client, "ATSH7DF")
        await send(client, "ATH0")
        await send(client, "ATZ", 2)

    # Save results
    results["timestamp"] = time.time()
    results["date"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)
    log(f"\nResults saved to {RESULTS_FILE}")
    log(f"Total PIDs found: {len(results['pids'])}")
    log(f"Headers with data: {len(results['headers'])}")
    log(f"Mode 21 PIDs: {len(results['mode21'])}")
    log(f"Mode 22 PIDs: {len(results['mode22'])}")

    # Restart OBD service
    os.system("sudo systemctl start car-hud-obd 2>/dev/null")
    log("OBD service restarted")


if __name__ == "__main__":
    log("=== OBD Deep Probe Starting ===")
    asyncio.run(probe())
    log("=== Probe Complete ===")
