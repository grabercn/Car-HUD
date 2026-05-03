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
SUMMARY_FILE = "/home/chrismslist/car-hud/obd_probe_summary.txt"
LOG_FILE = "/tmp/obd_probe.log"

# Human-readable PID names for Mode 01 PIDs 0x00-0x5F
PID_NAMES = {
    0x00: "PIDs supported [01-20]",
    0x01: "Monitor status since DTCs cleared",
    0x02: "Freeze DTC",
    0x03: "Fuel system status",
    0x04: "Calculated engine load",
    0x05: "Engine coolant temperature",
    0x06: "Short term fuel trim (Bank 1)",
    0x07: "Long term fuel trim (Bank 1)",
    0x08: "Short term fuel trim (Bank 2)",
    0x09: "Long term fuel trim (Bank 2)",
    0x0A: "Fuel pressure (gauge)",
    0x0B: "Intake manifold absolute pressure",
    0x0C: "Engine RPM",
    0x0D: "Vehicle speed",
    0x0E: "Timing advance",
    0x0F: "Intake air temperature",
    0x10: "Mass air flow sensor rate",
    0x11: "Throttle position",
    0x12: "Commanded secondary air status",
    0x13: "Oxygen sensors present (2 banks)",
    0x14: "O2 Sensor 1 (Bank 1, Sensor 1)",
    0x15: "O2 Sensor 2 (Bank 1, Sensor 2)",
    0x16: "O2 Sensor 3 (Bank 1, Sensor 3)",
    0x17: "O2 Sensor 4 (Bank 1, Sensor 4)",
    0x18: "O2 Sensor 5 (Bank 2, Sensor 1)",
    0x19: "O2 Sensor 6 (Bank 2, Sensor 2)",
    0x1A: "O2 Sensor 7 (Bank 2, Sensor 3)",
    0x1B: "O2 Sensor 8 (Bank 2, Sensor 4)",
    0x1C: "OBD standards compliance",
    0x1D: "Oxygen sensors present (4 banks)",
    0x1E: "Auxiliary input status",
    0x1F: "Run time since engine start",
    0x20: "PIDs supported [21-40]",
    0x21: "Distance traveled with MIL on",
    0x22: "Fuel rail pressure (relative to manifold vacuum)",
    0x23: "Fuel rail gauge pressure (diesel/gasoline direct inject)",
    0x24: "O2 Sensor 1 (wide range, lambda)",
    0x25: "O2 Sensor 2 (wide range, lambda)",
    0x26: "O2 Sensor 3 (wide range, lambda)",
    0x27: "O2 Sensor 4 (wide range, lambda)",
    0x28: "O2 Sensor 5 (wide range, lambda)",
    0x29: "O2 Sensor 6 (wide range, lambda)",
    0x2A: "O2 Sensor 7 (wide range, lambda)",
    0x2B: "O2 Sensor 8 (wide range, lambda)",
    0x2C: "Commanded EGR",
    0x2D: "EGR error",
    0x2E: "Commanded evaporative purge",
    0x2F: "Fuel tank level input",
    0x30: "Warm-ups since codes cleared",
    0x31: "Distance traveled since codes cleared",
    0x32: "Evap system vapor pressure",
    0x33: "Absolute barometric pressure",
    0x34: "O2 Sensor 1 (wide range, current)",
    0x35: "O2 Sensor 2 (wide range, current)",
    0x36: "O2 Sensor 3 (wide range, current)",
    0x37: "O2 Sensor 4 (wide range, current)",
    0x38: "O2 Sensor 5 (wide range, current)",
    0x39: "O2 Sensor 6 (wide range, current)",
    0x3A: "O2 Sensor 7 (wide range, current)",
    0x3B: "O2 Sensor 8 (wide range, current)",
    0x3C: "Catalyst temperature (Bank 1, Sensor 1)",
    0x3D: "Catalyst temperature (Bank 1, Sensor 2)",
    0x3E: "Catalyst temperature (Bank 2, Sensor 1)",
    0x3F: "Catalyst temperature (Bank 2, Sensor 2)",
    0x40: "PIDs supported [41-60]",
    0x41: "Monitor status this drive cycle",
    0x42: "Control module voltage",
    0x43: "Absolute load value",
    0x44: "Commanded air-fuel equivalence ratio",
    0x45: "Relative throttle position",
    0x46: "Ambient air temperature",
    0x47: "Absolute throttle position B",
    0x48: "Absolute throttle position C",
    0x49: "Accelerator pedal position D",
    0x4A: "Accelerator pedal position E",
    0x4B: "Accelerator pedal position F",
    0x4C: "Commanded throttle actuator",
    0x4D: "Time run with MIL on",
    0x4E: "Time since trouble codes cleared",
    0x4F: "Max values (fuel-air ratio, O2V, O2I, intake pressure)",
    0x50: "Max value for air flow rate from MAF sensor",
    0x51: "Fuel type",
    0x52: "Ethanol fuel percentage",
    0x53: "Absolute evap system vapor pressure",
    0x54: "Evap system vapor pressure",
    0x55: "Short term secondary O2 trim (Bank 1/3)",
    0x56: "Long term secondary O2 trim (Bank 1/3)",
    0x57: "Short term secondary O2 trim (Bank 2/4)",
    0x58: "Long term secondary O2 trim (Bank 2/4)",
    0x59: "Fuel rail absolute pressure",
    0x5A: "Relative accelerator pedal position",
    0x5B: "Hybrid battery pack remaining life",
    0x5C: "Engine oil temperature",
    0x5D: "Fuel injection timing",
    0x5E: "Engine fuel rate",
    0x5F: "Emission requirements to which vehicle is designed",
}


def pid_name(pid_hex):
    """Look up a human-readable name for a Mode 01 PID string like '010C'."""
    if pid_hex.startswith("01") and len(pid_hex) == 4:
        try:
            num = int(pid_hex[2:], 16)
            return PID_NAMES.get(num, f"PID 0x{num:02X}")
        except ValueError:
            pass
    if pid_hex.startswith("09"):
        mode09_names = {
            0x00: "Mode 09 supported PIDs",
            0x01: "VIN message count",
            0x02: "Vehicle Identification Number (VIN)",
            0x03: "Calibration ID message count",
            0x04: "Calibration ID",
            0x05: "CVN message count",
            0x06: "Calibration Verification Numbers",
            0x07: "Performance tracking message count",
            0x08: "In-use performance tracking (spark ignition)",
            0x09: "ECU name message count",
            0x0A: "ECU name",
            0x0B: "In-use performance tracking (compression)",
        }
        try:
            num = int(pid_hex[2:], 16)
            return mode09_names.get(num, f"Mode 09 PID 0x{num:02X}")
        except ValueError:
            pass
    return pid_hex


resp = ""
rdy = asyncio.Event()
results = {
    "pids": {},
    "headers": {},
    "mode21": {},
    "mode22": {},
    "mode03_dtc": {},
    "mode07_pending_dtc": {},
    "raw": [],
    "timing": {},
}


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def save_results():
    """Save current results to JSON (safe to call at any point for partial saves)."""
    results["timestamp"] = time.time()
    results["date"] = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(RESULTS_FILE, "w") as f:
            json.dump(results, f, indent=2)
    except Exception as e:
        log(f"WARNING: Failed to save JSON results: {e}")


def save_summary():
    """Write a human-readable text summary alongside the JSON."""
    lines = []
    lines.append("=" * 70)
    lines.append("  OBD-II DEEP PROBE SUMMARY")
    lines.append(f"  Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)

    # Timing
    if results.get("timing"):
        lines.append("")
        lines.append("--- TIMING ---")
        total = 0.0
        for phase, secs in results["timing"].items():
            lines.append(f"  {phase:40s} {secs:7.1f}s")
            total += secs
        lines.append(f"  {'TOTAL':40s} {total:7.1f}s")

    # ECU summary
    lines.append("")
    lines.append("--- ECUs THAT RESPONDED ---")
    responding_ecus = set()
    for hdr, pids in results.get("headers", {}).items():
        if pids:
            responding_ecus.add(hdr)
            lines.append(f"  {hdr}: {len(pids)} PIDs responded")
            for p, info in pids.items():
                name = info.get("name", p)
                lines.append(f"    {p} - {name}")
    if not responding_ecus:
        lines.append("  (none found)")

    # Mode 01 PIDs
    mode01 = {k: v for k, v in results.get("pids", {}).items() if k.startswith("01")}
    if mode01:
        lines.append("")
        lines.append(f"--- MODE 01 STANDARD PIDs ({len(mode01)} found) ---")
        for p in sorted(mode01.keys()):
            name = pid_name(p)
            raw = mode01[p]
            # Truncate raw response for readability
            display_raw = raw[:80] + "..." if len(raw) > 80 else raw
            lines.append(f"  {p}  {name:50s}  {display_raw}")

    # Mode 09 PIDs
    mode09 = {k: v for k, v in results.get("pids", {}).items() if k.startswith("09")}
    if mode09:
        lines.append("")
        lines.append(f"--- MODE 09 VEHICLE INFO ({len(mode09)} found) ---")
        for p in sorted(mode09.keys()):
            name = pid_name(p)
            raw = mode09[p]
            display_raw = raw[:80] + "..." if len(raw) > 80 else raw
            lines.append(f"  {p}  {name:50s}  {display_raw}")

    # DTCs
    dtc_stored = results.get("mode03_dtc", {})
    dtc_pending = results.get("mode07_pending_dtc", {})
    lines.append("")
    lines.append("--- DIAGNOSTIC TROUBLE CODES ---")
    if dtc_stored:
        lines.append(f"  Stored DTCs (Mode 03):")
        for hdr, raw in dtc_stored.items():
            lines.append(f"    [{hdr}] {raw}")
    else:
        lines.append("  Stored DTCs (Mode 03): none")
    if dtc_pending:
        lines.append(f"  Pending DTCs (Mode 07):")
        for hdr, raw in dtc_pending.items():
            lines.append(f"    [{hdr}] {raw}")
    else:
        lines.append("  Pending DTCs (Mode 07): none")

    # Mode 21 / 22
    if results.get("mode21"):
        lines.append("")
        lines.append(f"--- MODE 21 HONDA MANUFACTURER ({len(results['mode21'])} found) ---")
        for key in sorted(results["mode21"].keys()):
            raw = results["mode21"][key]
            display_raw = raw[:80] + "..." if len(raw) > 80 else raw
            lines.append(f"  {key:25s}  {display_raw}")

    if results.get("mode22"):
        lines.append("")
        lines.append(f"--- MODE 22 EXTENDED DIAGNOSTICS ({len(results['mode22'])} found) ---")
        for key in sorted(results["mode22"].keys()):
            raw = results["mode22"][key]
            display_raw = raw[:80] + "..." if len(raw) > 80 else raw
            lines.append(f"  {key:25s}  {display_raw}")

    # Totals
    lines.append("")
    lines.append("--- TOTALS ---")
    lines.append(f"  Mode 01 PIDs:      {len(mode01)}")
    lines.append(f"  Mode 09 PIDs:      {len(mode09)}")
    lines.append(f"  ECU headers:       {len(results.get('headers', {}))}")
    lines.append(f"  Mode 21 PIDs:      {len(results.get('mode21', {}))}")
    lines.append(f"  Mode 22 PIDs:      {len(results.get('mode22', {}))}")
    lines.append(f"  Stored DTCs:       {len(dtc_stored)}")
    lines.append(f"  Pending DTCs:      {len(dtc_pending)}")
    lines.append("=" * 70)

    try:
        with open(SUMMARY_FILE, "w") as f:
            f.write("\n".join(lines) + "\n")
        log(f"Text summary saved to {SUMMARY_FILE}")
    except Exception as e:
        log(f"WARNING: Failed to save text summary: {e}")


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


def has_data(raw_resp):
    """Return True if the ELM327 response contains actual data (not an error)."""
    clean = raw_resp.replace(" ", "").replace("\r", "").replace("\n", "")
    upper = clean.upper()
    if "NODATA" in upper or "ERROR" in upper or "?" in clean:
        return False
    return len(clean) > 4


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
            return

        # Phase 1: Supported PID ranges
        t0 = time.monotonic()
        log("\n=== PHASE 1: Supported PID ranges ===")
        for base in ["0100", "0120", "0140", "0160", "0180", "01A0", "01C0"]:
            r = await send(client, base, 3)
            clean = r.replace(" ", "").replace("\r", "").replace("\n", "")
            if "NODATA" not in clean.upper() and len(clean) > 6:
                log(f"  {base} ({pid_name(base)}): {r}")
                results["pids"][base] = r
        results["timing"]["Phase 1 - PID support ranges"] = time.monotonic() - t0
        save_results()

        # Phase 2: Every standard PID 01-7F
        t0 = time.monotonic()
        log("\n=== PHASE 2: All Mode 01 PIDs ===")
        for pid_num in range(0x00, 0x80):
            pid = f"01{pid_num:02X}"
            r = await send(client, pid, 2)
            if has_data(r):
                log(f"  {pid} ({pid_name(pid)}): {r}")
                results["pids"][pid] = r
        results["timing"]["Phase 2 - Mode 01 PIDs"] = time.monotonic() - t0
        save_results()

        # Phase 3: Try ALL ECU headers with key PIDs
        t0 = time.monotonic()
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
        results["timing"]["Phase 3 - ECU header scan"] = time.monotonic() - t0
        save_results()

        # Phase 4: Mode 03 (stored DTCs) and Mode 07 (pending DTCs)
        t0 = time.monotonic()
        log("\n=== PHASE 4: Mode 03 (Stored DTCs) & Mode 07 (Pending DTCs) ===")
        dtc_headers = ["7DF", "7E0", "7E1", "7E2", "7E4"]
        for hdr in dtc_headers:
            await send(client, f"ATSH{hdr}")
            # Mode 03 — stored DTCs
            r = await send(client, "03", 4)
            if has_data(r):
                log(f"  [{hdr}] Mode 03 (stored DTC): {r}")
                results["mode03_dtc"][hdr] = r
            # Mode 07 — pending DTCs
            r = await send(client, "07", 4)
            if has_data(r):
                log(f"  [{hdr}] Mode 07 (pending DTC): {r}")
                results["mode07_pending_dtc"][hdr] = r
        if not results["mode03_dtc"] and not results["mode07_pending_dtc"]:
            log("  No stored or pending DTCs found.")
        results["timing"]["Phase 4 - DTC reads (Mode 03/07)"] = time.monotonic() - t0
        save_results()

        # Phase 5: Mode 21 with different headers
        t0 = time.monotonic()
        log("\n=== PHASE 5: Mode 21 (Honda Manufacturer) ===")
        for hdr in ["7E0", "7E2", "7E4", "7DF"]:
            await send(client, f"ATSH{hdr}")
            for pid_num in range(0x01, 0x60):
                pid = f"21{pid_num:02X}"
                r = await send(client, pid, 2)
                if has_data(r):
                    key = f"{hdr}/{pid}"
                    log(f"  [{hdr}] {pid}: {r}")
                    results["mode21"][key] = r
        results["timing"]["Phase 5 - Mode 21 Honda"] = time.monotonic() - t0
        save_results()

        # Phase 6: Mode 22 with different headers
        t0 = time.monotonic()
        log("\n=== PHASE 6: Mode 22 (Extended Diagnostics) ===")
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
        results["timing"]["Phase 6 - Mode 22 extended"] = time.monotonic() - t0
        save_results()

        # Phase 7: Mode 09 (Vehicle info)
        t0 = time.monotonic()
        log("\n=== PHASE 7: Mode 09 (Vehicle Info) ===")
        await send(client, "ATSH7DF")
        for pid_num in range(0x00, 0x0F):
            pid = f"09{pid_num:02X}"
            r = await send(client, pid, 3)
            clean = r.replace(" ", "").replace("\r", "").replace("\n", "")
            if "NODATA" not in clean.upper() and len(clean) > 4:
                log(f"  {pid} ({pid_name(pid)}): {r}")
                results["pids"][pid] = r
        results["timing"]["Phase 7 - Mode 09 vehicle info"] = time.monotonic() - t0
        save_results()

        # Reset ELM327 to defaults
        await send(client, "ATSH7DF")
        await send(client, "ATH0")
        await send(client, "ATZ", 2)

    # Final save
    save_results()
    save_summary()

    log(f"\nResults saved to {RESULTS_FILE}")
    log(f"Summary saved to {SUMMARY_FILE}")
    log(f"Total PIDs found: {len(results['pids'])}")
    log(f"Headers with data: {len(results['headers'])}")
    log(f"Mode 21 PIDs: {len(results['mode21'])}")
    log(f"Mode 22 PIDs: {len(results['mode22'])}")
    log(f"Stored DTCs: {len(results['mode03_dtc'])}")
    log(f"Pending DTCs: {len(results['mode07_pending_dtc'])}")


if __name__ == "__main__":
    probe_start = time.monotonic()
    log("=== OBD Deep Probe Starting ===")
    try:
        asyncio.run(probe())
    except Exception as e:
        log(f"PROBE CRASHED: {e}")
        import traceback
        log(traceback.format_exc())
        # Save whatever we have so far
        results["crash"] = str(e)
        save_results()
        save_summary()
        log(f"Partial results saved to {RESULTS_FILE}")
    finally:
        elapsed = time.monotonic() - probe_start
        results["timing"]["Total wall-clock time"] = elapsed
        save_results()
        log(f"Total elapsed time: {elapsed:.1f}s")
        os.system("sudo systemctl start car-hud-obd 2>/dev/null")
        log("OBD service restarted (finally block)")
    log("=== Probe Complete ===")
