#!/usr/bin/env python3
"""OBD Bridge — runs on laptop, reads OBD data, sends to Pi via HTTP.
The Pi's OBD service reads from /tmp/car-hud-obd-data as usual.
This script writes that file remotely via SSH.

Usage: python obd_bridge.py COM3
"""

import obd
import json
import time
import sys
import subprocess

PI_HOST = "172.20.10.2"
OBD_FILE = "/tmp/car-hud-obd-data"

CRITICAL = ["STATUS", "COOLANT_TEMP", "ENGINE_LOAD", "HYBRID_BATTERY_REMAINING"]
STANDARD = ["RPM", "SPEED", "THROTTLE_POS", "FUEL_LEVEL", "CONTROL_MODULE_VOLTAGE",
            "CATALYST_TEMP_B1S1", "MAF", "FUEL_TYPE", "ABSOLUTE_LOAD",
            "BAROMETRIC_PRESSURE", "INTAKE_TEMP"]


def send_to_pi(data):
    """Write OBD data to Pi via SSH."""
    payload = json.dumps(data).replace('"', '\\"')
    try:
        subprocess.run(
            ["ssh", "-o", "ConnectTimeout=3", f"chrismslist@{PI_HOST}",
             f'echo "{payload}" > {OBD_FILE}'],
            capture_output=True, timeout=5)
    except Exception:
        pass


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "COM3"
    print(f"Connecting to OBD on {port}...")

    conn = obd.OBD(port, baudrate=38400, fast=False, timeout=15)
    print(f"Status: {conn.status()}")
    print(f"Protocol: {conn.protocol_name()}")

    if conn.status() != obd.OBDStatus.CAR_CONNECTED:
        print("Not connected!")
        return

    print(f"Bridging OBD data to Pi at {PI_HOST}...")
    print("Press Ctrl+C to stop")

    while True:
        data = {}
        warnings = []

        for pid_name in CRITICAL + STANDARD:
            try:
                cmd = getattr(obd.commands, pid_name, None)
                if cmd and conn.supports(cmd):
                    resp = conn.query(cmd)
                    if not resp.is_null():
                        val = resp.value
                        if hasattr(val, 'magnitude'):
                            data[pid_name] = val.magnitude
                        else:
                            data[pid_name] = str(val)

                        if pid_name == "STATUS" and hasattr(resp.value, 'MIL'):
                            if resp.value.MIL:
                                warnings.append("CHECK ENGINE")
                        elif pid_name == "COOLANT_TEMP":
                            v = val.magnitude if hasattr(val, 'magnitude') else 0
                            if v > 110:
                                warnings.append(f"HOT COOLANT {v:.0f}C")
                        elif pid_name == "HYBRID_BATTERY_REMAINING":
                            v = val.magnitude if hasattr(val, 'magnitude') else 0
                            if v < 15:
                                warnings.append(f"LOW HV BATT {v:.0f}%")
            except Exception:
                pass

        # Check DTCs
        try:
            dtc_resp = conn.query(obd.commands.GET_DTC)
            if not dtc_resp.is_null() and dtc_resp.value:
                dtcs = [(code, desc) for code, desc in dtc_resp.value]
                if dtcs:
                    warnings.append(f"{len(dtcs)} DTC(s)")
            else:
                dtcs = []
        except Exception:
            dtcs = []

        payload = {
            "connected": True,
            "status": "connected",
            "protocol": conn.protocol_name(),
            "adapter": "Vgate iCar Pro 2S",
            "dtcs": dtcs,
            "warnings": warnings,
            "data": data,
            "timestamp": time.time()
        }

        # Print summary
        rpm = data.get("RPM", 0)
        speed = data.get("SPEED", 0)
        fuel = data.get("FUEL_LEVEL", 0)
        hv = data.get("HYBRID_BATTERY_REMAINING", 0)
        cool = data.get("COOLANT_TEMP", 0)
        warn = " | ".join(warnings) if warnings else "OK"
        print(f"\r  RPM:{rpm:5.0f}  SPD:{speed:3.0f}km/h  FUEL:{fuel:4.1f}%  HV:{hv:4.1f}%  COOL:{cool:3.0f}C  [{warn}]", end="", flush=True)

        send_to_pi(payload)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
