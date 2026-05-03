#!/usr/bin/env python3
"""Car-HUD Honda Accord Hybrid Battery Monitor
Tracks HV battery health over time using OBD-II data.
2014 Accord Hybrid: 72 cells × 3.6V = ~260V Li-ion pack.

Reads available PIDs and derives health metrics:
- SOC (State of Charge): PID 015B
- Pack voltage: derived from cell voltage × 72 or Mode 22
- Discharge/regen rates: calculated from voltage delta over time
- Temperature: if available via Mode 22
- Health estimation: voltage stability, SOC recovery patterns

Stores historical data in SQLite for trend analysis.
"""

import os
import json
import time
import sqlite3
import threading
from datetime import datetime

DATA_FILE = "/tmp/car-hud-battery-data"
DB_PATH = "/home/chrismslist/car-hud/battery_history.db"
OBD_FILE = "/tmp/car-hud-obd-data"

# 2014 Honda Accord Hybrid specs
PACK_CELLS = 72
CELL_NOMINAL_V = 3.6
PACK_NOMINAL_V = PACK_CELLS * CELL_NOMINAL_V  # ~259.2V
PACK_MIN_V = PACK_CELLS * 3.0   # ~216V (discharged)
PACK_MAX_V = PACK_CELLS * 4.1   # ~295.2V (fully charged)
CAPACITY_KWH = 1.3

# Recording interval
RECORD_INTERVAL = 30  # seconds between database writes


def init_db():
    """Create battery history database."""
    db = sqlite3.connect(DB_PATH)
    db.execute("""CREATE TABLE IF NOT EXISTS battery_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
        date TEXT NOT NULL,
        soc REAL,
        pack_voltage REAL,
        pack_current REAL,
        temperature REAL,
        cell_delta REAL,
        power_kw REAL,
        is_charging INTEGER,
        is_regen INTEGER,
        speed REAL,
        rpm REAL,
        raw_data TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS battery_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_time REAL,
        end_time REAL,
        start_soc REAL,
        end_soc REAL,
        min_soc REAL,
        max_soc REAL,
        distance_mi REAL,
        avg_power_kw REAL,
        regen_pct REAL
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON battery_log(timestamp)")
    db.commit()
    return db


class BatteryMonitor:
    def __init__(self):
        self.db = init_db()
        self.last_record_time = 0
        self.session_start = 0
        self.session_start_soc = 0
        self.min_soc = 100
        self.max_soc = 0
        self.total_distance = 0
        self.power_samples = []
        self.regen_count = 0
        self.total_samples = 0

        # Voltage tracking for health analysis
        self.voltage_history = []  # last 60 readings for delta calculation
        self.soc_history = []

        # Derived metrics
        self.current_data = {
            "connected": False,
            "soc": 0,
            "pack_voltage": 0,
            "pack_current": 0,
            "temperature": 0,
            "cell_avg_v": 0,
            "cell_delta_v": 0,
            "power_kw": 0,
            "is_charging": False,
            "is_regen": False,
            "discharge_rate": 0,  # V/min
            "soc_rate": 0,  # %/min
            "health_score": 0,  # 0-100
            "session_kwh": 0,
            "session_regen_pct": 0,
        }

    def read_obd(self):
        """Read OBD data and extract battery metrics."""
        try:
            with open(OBD_FILE) as f:
                obd = json.load(f)
        except Exception:
            return None

        if not obd.get("connected"):
            return None

        data = obd.get("data", {})
        if not data:
            return None

        now = time.time()

        # Extract what we can from standard PIDs
        soc = data.get("HYBRID_BATTERY_REMAINING", 0)
        voltage = data.get("CONTROL_MODULE_VOLTAGE", 0)  # 12V system
        rpm = data.get("RPM", 0)
        speed = data.get("SPEED", 0) * 0.621371  # km/h to mph
        throttle = data.get("THROTTLE_POS", 0)
        load = data.get("ENGINE_LOAD", 0)

        # Estimate pack voltage from SOC (linear approximation)
        # Real data would come from Mode 22 PIDs
        estimated_pack_v = PACK_MIN_V + (soc / 100) * (PACK_MAX_V - PACK_MIN_V)

        # Estimate power from engine load and speed
        # Positive = discharging, Negative = regen
        is_ev = rpm < 100
        is_regen = not is_ev and throttle < 5 and speed > 5
        is_charging = is_regen

        # Rough power estimate (kW)
        if is_regen:
            power_kw = -(load / 100) * 15  # regen: up to -15kW
        elif is_ev:
            power_kw = (throttle / 100) * 30  # EV: up to 30kW
        else:
            power_kw = (load / 100) * 20 * (1 - throttle / 200)  # hybrid assist

        cell_avg = estimated_pack_v / PACK_CELLS

        # Track voltage delta (stability indicator)
        self.voltage_history.append((now, estimated_pack_v))
        self.soc_history.append((now, soc))

        # Keep last 5 minutes of history
        cutoff = now - 300
        self.voltage_history = [(t, v) for t, v in self.voltage_history if t > cutoff]
        self.soc_history = [(t, s) for t, s in self.soc_history if t > cutoff]

        # Calculate rates
        discharge_rate = 0  # V/min
        soc_rate = 0  # %/min
        if len(self.voltage_history) >= 2:
            dt = (self.voltage_history[-1][0] - self.voltage_history[0][0]) / 60
            if dt > 0.1:
                discharge_rate = (self.voltage_history[-1][1] - self.voltage_history[0][1]) / dt
        if len(self.soc_history) >= 2:
            dt = (self.soc_history[-1][0] - self.soc_history[0][0]) / 60
            if dt > 0.1:
                soc_rate = (self.soc_history[-1][1] - self.soc_history[0][1]) / dt

        # Voltage stability (cell delta estimate)
        # Real cell delta would come from individual cell readings
        # We estimate from SOC behavior — erratic SOC = high cell imbalance
        cell_delta = 0
        if len(self.soc_history) > 10:
            soc_vals = [s for _, s in self.soc_history[-20:]]
            if len(soc_vals) > 5:
                # Variance of SOC readings — high variance = unstable = poor health
                mean_soc = sum(soc_vals) / len(soc_vals)
                variance = sum((s - mean_soc) ** 2 for s in soc_vals) / len(soc_vals)
                cell_delta = min(variance * 0.01, 0.5)  # map to 0-0.5V range

        # Health score (0-100)
        # Based on: SOC range, voltage stability, regen recovery
        health = 100
        if cell_delta > 0.1:
            health -= int(cell_delta * 100)
        if soc < 20:
            health -= 10
        if abs(discharge_rate) > 5:
            health -= 5  # rapid voltage swings
        health = max(0, min(100, health))

        # Session tracking
        if self.session_start == 0:
            self.session_start = now
            self.session_start_soc = soc
        self.min_soc = min(self.min_soc, soc)
        self.max_soc = max(self.max_soc, soc)
        self.total_samples += 1
        if is_regen:
            self.regen_count += 1
        self.power_samples.append(power_kw)

        self.current_data.update({
            "connected": True,
            "soc": soc,
            "pack_voltage": round(estimated_pack_v, 1),
            "pack_current": round(power_kw / (estimated_pack_v / 1000) if estimated_pack_v > 0 else 0, 1),
            "temperature": 0,  # needs Mode 22 PID
            "cell_avg_v": round(cell_avg, 3),
            "cell_delta_v": round(cell_delta, 3),
            "power_kw": round(power_kw, 1),
            "is_charging": is_charging,
            "is_regen": is_regen,
            "discharge_rate": round(discharge_rate, 2),
            "soc_rate": round(soc_rate, 2),
            "health_score": health,
            "speed": round(speed, 1),
            "rpm": rpm,
            "session_min_soc": self.min_soc,
            "session_max_soc": self.max_soc,
            "session_regen_pct": round(self.regen_count / max(1, self.total_samples) * 100, 1),
            "voltage_trend": [v for _, v in self.voltage_history[-30:]],
            "soc_trend": [s for _, s in self.soc_history[-30:]],
        })

        return self.current_data

    def record_to_db(self, data):
        """Write a data point to the database."""
        now = time.time()
        if now - self.last_record_time < RECORD_INTERVAL:
            return
        self.last_record_time = now

        try:
            self.db.execute("""INSERT INTO battery_log
                (timestamp, date, soc, pack_voltage, pack_current, temperature,
                 cell_delta, power_kw, is_charging, is_regen, speed, rpm, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (now, datetime.now().isoformat(),
                 data["soc"], data["pack_voltage"], data["pack_current"],
                 data["temperature"], data["cell_delta_v"], data["power_kw"],
                 1 if data["is_charging"] else 0,
                 1 if data["is_regen"] else 0,
                 data["speed"], data["rpm"],
                 json.dumps({k: v for k, v in data.items()
                            if k not in ("voltage_trend", "soc_trend")})))
            self.db.commit()
        except Exception:
            pass

    def get_history(self, hours=24):
        """Get historical data for graphing."""
        cutoff = time.time() - hours * 3600
        try:
            rows = self.db.execute(
                """SELECT timestamp, soc, pack_voltage, power_kw, cell_delta,
                          is_regen, speed FROM battery_log
                   WHERE timestamp > ? ORDER BY timestamp""",
                (cutoff,)).fetchall()
            return [{
                "t": r[0], "soc": r[1], "v": r[2], "kw": r[3],
                "delta": r[4], "regen": r[5], "speed": r[6]
            } for r in rows]
        except Exception:
            return []

    def publish(self):
        """Write current data to shared file."""
        try:
            out = dict(self.current_data)
            out["timestamp"] = time.time()
            out["history_count"] = self.db.execute(
                "SELECT COUNT(*) FROM battery_log").fetchone()[0]
            with open(DATA_FILE, "w") as f:
                json.dump(out, f)
        except Exception:
            pass

    def run(self):
        """Main loop — reads OBD, updates metrics, records history."""
        while True:
            data = self.read_obd()
            if data:
                self.record_to_db(data)
                self.publish()
            else:
                self.current_data["connected"] = False
                self.publish()
            time.sleep(1)


def main():
    print("[Battery] Honda Accord Hybrid battery monitor starting...", flush=True)
    monitor = BatteryMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
