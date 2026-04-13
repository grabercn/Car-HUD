#!/usr/bin/env python3
"""Honda Accord OBD-II Service
Connects to Bluetooth OBD-II adapter, reads vehicle data,
writes to signal file for HUD to display.
Auto-reconnects if adapter disconnects.

For 2014 Honda Accord Hybrid.
"""

import os
import sys
import json
import time
import subprocess

SIGNAL_FILE = "/tmp/car-hud-obd-data"
LOG_FILE = "/tmp/car-hud-obd.log"

# Known Bluetooth OBD-II adapter names/MACs
OBD_BT_NAMES = ["obd", "elm", "elm327", "vlink", "obdii", "car scanner", "veepeak", "v-link", "scan", "android-vlink", "icar"]
OBD_RFCOMM_DEV = "/dev/rfcomm0"

# Key PIDs to monitor continuously
CRITICAL_PIDS = [
    "STATUS",                # MIL (check engine) status
    "COOLANT_TEMP",          # Engine coolant temperature
    "ENGINE_LOAD",           # Calculated engine load
    "HYBRID_BATTERY_REMAINING",  # Hybrid battery SOC
]

STANDARD_PIDS = [
    "RPM",                   # Engine RPM
    "SPEED",                 # Vehicle speed
    "THROTTLE_POS",          # Throttle position
    "FUEL_LEVEL",            # Fuel level
    "INTAKE_TEMP",           # Intake air temperature
    "RUN_TIME",              # Engine run time
    "CONTROL_MODULE_VOLTAGE",# Battery voltage
    "CATALYST_TEMP_B1S1",    # Catalytic converter temp
    "TIMING_ADVANCE",        # Timing advance
    "MAF",                   # Mass air flow
    "FUEL_TYPE",             # Fuel type (hybrid detection)
    "ABSOLUTE_LOAD",         # Absolute engine load
    "BAROMETRIC_PRESSURE",   # Barometric pressure
    "DISTANCE_SINCE_DTC_CLEAR", # Distance since last clear
]

# DTCs (Diagnostic Trouble Codes) — check periodically
DTC_CHECK_INTERVAL = 30  # seconds


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


def write_obd_data(data):
    """Write OBD data to signal file for HUD."""
    data["timestamp"] = time.time()
    try:
        with open(SIGNAL_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        log(f"Signal write error: {e}")


def find_obd_adapter():
    """Scan for Bluetooth OBD-II adapter."""
    try:
        result = subprocess.run(
            ["bluetoothctl", "devices"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split(" ", 2)
            if len(parts) >= 3:
                mac = parts[1]
                name = parts[2].lower()
                for obd_name in OBD_BT_NAMES:
                    if obd_name in name:
                        log(f"Found OBD adapter: {parts[2]} ({mac})")
                        return mac, parts[2]
    except Exception as e:
        log(f"BT scan error: {e}")
    return None, None


def bind_rfcomm(mac):
    """Bind Bluetooth MAC to /dev/rfcomm0."""
    try:
        subprocess.run(["sudo", "rfcomm", "release", "0"], timeout=5,
                       capture_output=True)
        time.sleep(0.5)
        result = subprocess.run(
            ["sudo", "rfcomm", "bind", "0", mac],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            log(f"Bound {mac} to {OBD_RFCOMM_DEV}")
            return True
        else:
            log(f"rfcomm bind failed: {result.stderr}")
    except Exception as e:
        log(f"rfcomm error: {e}")
    return False


def main():
    import obd

    log("OBD-II service starting...")

    # Write initial status
    write_obd_data({
        "connected": False,
        "status": "searching",
        "dtcs": [],
        "warnings": [],
        "data": {}
    })

    connection = None
    last_dtc_check = 0
    obd_data = {
        "connected": False,
        "status": "searching",
        "dtcs": [],
        "warnings": [],
        "data": {},
        "adapter": ""
    }

    while True:
        # --- Connection phase ---
        if connection is None or connection.status() != obd.OBDStatus.CAR_CONNECTED:
            obd_data["connected"] = False
            obd_data["status"] = "searching"
            write_obd_data(obd_data)

            # Try to find and connect to OBD adapter
            mac, name = find_obd_adapter()
            if mac:
                obd_data["adapter"] = name
                obd_data["status"] = "connecting"
                write_obd_data(obd_data)

                if bind_rfcomm(mac):
                    time.sleep(2)
                    try:
                        connection = obd.OBD(OBD_RFCOMM_DEV, baudrate=38400,
                                             fast=False, timeout=10)
                        if connection.status() == obd.OBDStatus.CAR_CONNECTED:
                            log(f"Connected to vehicle via {name}")
                            obd_data["connected"] = True
                            obd_data["status"] = "connected"
                            obd_data["protocol"] = str(connection.protocol_name())
                            write_obd_data(obd_data)
                        else:
                            log(f"OBD status: {connection.status()}")
                            obd_data["status"] = str(connection.status())
                            write_obd_data(obd_data)
                            connection = None
                    except Exception as e:
                        log(f"OBD connect error: {e}")
                        obd_data["status"] = "error"
                        write_obd_data(obd_data)
                        connection = None
            else:
                obd_data["status"] = "no adapter"

            write_obd_data(obd_data)
            time.sleep(10)
            continue

        # --- Data reading phase ---
        try:
            data = {}
            warnings = []

            # Read critical PIDs
            for pid_name in CRITICAL_PIDS:
                try:
                    cmd = getattr(obd.commands, pid_name, None)
                    if cmd and connection.supports(cmd):
                        resp = connection.query(cmd)
                        if not resp.is_null():
                            val = resp.value
                            if hasattr(val, 'magnitude'):
                                val = val.magnitude
                            data[pid_name] = val

                            # Check for warnings
                            if pid_name == "STATUS" and hasattr(resp.value, 'MIL'):
                                if resp.value.MIL:
                                    warnings.append("CHECK ENGINE LIGHT ON")
                            elif pid_name == "COOLANT_TEMP":
                                if isinstance(val, (int, float)) and val > 110:
                                    warnings.append(f"HIGH COOLANT: {val:.0f}C")
                            elif pid_name == "ENGINE_LOAD":
                                if isinstance(val, (int, float)) and val > 90:
                                    warnings.append(f"HIGH LOAD: {val:.0f}%")
                except Exception:
                    pass

            # Read standard PIDs
            for pid_name in STANDARD_PIDS:
                try:
                    cmd = getattr(obd.commands, pid_name, None)
                    if cmd and connection.supports(cmd):
                        resp = connection.query(cmd)
                        if not resp.is_null():
                            val = resp.value
                            if hasattr(val, 'magnitude'):
                                val = val.magnitude
                            data[pid_name] = val
                except Exception:
                    pass

            # Check DTCs periodically
            now = time.time()
            if now - last_dtc_check > DTC_CHECK_INTERVAL:
                last_dtc_check = now
                try:
                    dtc_resp = connection.query(obd.commands.GET_DTC)
                    if not dtc_resp.is_null() and dtc_resp.value:
                        dtcs = [(code, desc) for code, desc in dtc_resp.value]
                        obd_data["dtcs"] = dtcs
                        if dtcs:
                            warnings.append(f"{len(dtcs)} DTC(s) ACTIVE")
                            for code, desc in dtcs[:3]:
                                log(f"DTC: {code} - {desc}")
                    else:
                        obd_data["dtcs"] = []
                except Exception:
                    pass

            obd_data["data"] = data
            obd_data["warnings"] = warnings
            obd_data["connected"] = True
            obd_data["status"] = "connected"
            write_obd_data(obd_data)

        except Exception as e:
            log(f"Read error: {e}")
            obd_data["connected"] = False
            obd_data["status"] = "disconnected"
            write_obd_data(obd_data)
            connection = None

        time.sleep(0.5)  # ~2 updates per second


if __name__ == "__main__":
    main()
