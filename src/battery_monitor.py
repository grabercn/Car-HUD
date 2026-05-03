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

# ============================================================================
# 2014 Honda Accord Hybrid (9th Gen) -- HV Battery Research Notes
# ============================================================================
#
# PACK CONFIGURATION:
#   - 72 lithium-ion cells connected in series
#   - Nominal cell voltage: 3.6V (standard Li-ion NMC range: 2.5V-4.2V)
#   - Pack nominal voltage: 72 x 3.6V = 259.2V
#   - Pack voltage range: ~216V (discharged) to ~295.2V (fully charged)
#   - Total energy capacity: 1.3 kWh
#   - Estimated cell capacity: ~5 Ah (per Blue Energy EHW-series spec sheets;
#     1.3 kWh / 259.2V = ~5.015 Ah, consistent with 5Ah cells found in later
#     Accord Hybrid modules listed at 3.7V/5Ah OEM)
#
# CELL CHEMISTRY:
#   - Lithium-ion (Li-ion), likely NMC (Nickel Manganese Cobalt) or similar
#   - Manufactured by Blue Energy Co., Ltd. (Honda / GS Yuasa joint venture)
#   - Blue Energy EHW-series cells, prismatic format
#   - Cell specs (EHW5 reference): 3.6V nominal, 5Ah, 120mm x 12.5mm x 85mm,
#     energy density ~78.6 Wh/kg, max current 300A
#   - Note: the 2014 model predates the EHW5 (introduced 2016); the 2014 uses
#     an earlier EHW variant with similar chemistry but slightly larger form
#
# SOC OPERATING RANGE (Honda BMS strategy):
#   - Honda limits usable SOC to approximately 20%-80% of true cell capacity
#   - The reported "0-100%" SOC on the dashboard maps to this ~60% usable window
#   - This buffer protects cells from deep discharge (<2.5V) and overcharge (>4.2V)
#   - During highway driving, battery typically cycles between 20-50% displayed SOC
#   - Honda targets keeping the pack near 50-60% SOC for optimal power availability
#
# CELL VOLTAGE RANGES (per cell):
#   - Nominal: 3.6V
#   - Fully charged: 4.2V (absolute max, BMS-limited)
#   - Fully discharged: 2.5V (absolute min cutoff)
#   - Normal operating range: ~3.0V (BMS low limit) to ~4.1V (BMS high limit)
#   - Typical cycling range under Honda BMS: ~3.3V to ~3.9V (within SOC window)
#
# CELL DELTA VOLTAGE (voltage spread between cells):
#   - New/healthy pack: <20 mV (0.020V) spread between strongest/weakest cell
#   - Acceptable aging: <50 mV (0.050V)
#   - Needs attention: 50-100 mV (0.050-0.100V) -- cell imbalance developing
#   - Degraded/failing: >100-200 mV (0.100-0.200V) -- replacement likely needed
#   - The BMS continuously balances cells; rising delta = aging or failed cell
#
# OPERATING TEMPERATURE:
#   - Blue Energy EHW cell rated range: -30C to +55C (-22F to 131F)
#   - Optimal performance: 20C to 30C (68F to 86F)
#   - Honda triggers "Battery Temperature at Limit" warning at high temps,
#     reducing hybrid power to protect the pack
#   - Cold weather (<0C/32F) reduces effective capacity and regen capability
#   - Air-cooled battery with dedicated cooling fan behind rear seat
#
# EXPECTED LIFESPAN:
#   - Warranty: 8 years / 100,000 mi (federal); 10 years / 150,000 mi (CARB)
#   - Real-world: 8-15 years, 100,000-200,000+ miles under normal conditions
#   - NMC cell cycle life: ~1,000-2,000 full charge/discharge cycles to 80% cap
#   - At pack level with Honda's conservative SOC window and micro-cycling,
#     effective cycle life is extended significantly beyond raw cell ratings
#   - Hybrid packs see many shallow micro-cycles rather than full depth cycles,
#     which is far less stressful than full charge/discharge cycling
#
# KNOWN DEGRADATION PATTERNS:
#   - Gradual capacity fade: 1-2% per year under normal conditions
#   - Cell imbalance increases with age -- one weak cell drags down the pack
#   - High-temperature exposure accelerates degradation (hot climates)
#   - Reduced regen recovery rate is an early sign of capacity loss
#   - Erratic SOC readings indicate cell imbalance (BMS reports averaged data)
#   - Internal resistance increases with age, reducing power output capability
#   - Frequent stop-and-go + extreme temperatures = fastest degradation path
#   - Honda Accord Plug-In Hybrid (PHEV) variant had known early battery
#     deterioration (warranty extended to 12yr/200k mi); standard hybrid
#     has been more reliable
#
# Sources:
#   - Honda official specs: hondanews.com/en-US/honda-automobiles/releases
#   - Honda Owners: owners.honda.com/vehicles/information/2014/Accord-Hybrid
#   - Blue Energy / GS Yuasa: gs-yuasa.com/en/newsrelease
#   - Honda Emergency Response Guide: honda.ca (2014-2017 Accord Hybrid ERG)
#   - Greentec Auto technical data: greentecauto.com
#   - Midtronics hybrid battery diagnostics: midtronics.com/blog
#   - Battery University: batteryuniversity.com
#   - DriveAccord forum community data: driveaccord.net
# ============================================================================

import os
import json
import time
import sqlite3
import threading
from datetime import datetime

DATA_FILE = "/tmp/car-hud-battery-data"
DB_PATH = "/home/chrismslist/car-hud/battery_history.db"
OBD_FILE = "/tmp/car-hud-obd-data"

# 2014 Honda Accord Hybrid specs (verified via research -- see notes above)
PACK_CELLS = 72                                  # 72 cells in series
CELL_NOMINAL_V = 3.6                             # Li-ion NMC nominal voltage
PACK_NOMINAL_V = PACK_CELLS * CELL_NOMINAL_V     # 259.2V nominal
PACK_MIN_V = PACK_CELLS * 3.0                    # ~216V (BMS low cutoff)
PACK_MAX_V = PACK_CELLS * 4.1                    # ~295.2V (BMS high limit)
CAPACITY_KWH = 1.3                               # Total pack energy
FACTORY_CAPACITY_AH = 5.0                        # ~5Ah per cell (1.3kWh / 259.2V)

# Factory-new reference values (2014 Accord Hybrid when new)
FACTORY_SOC_RANGE = (20, 80)   # Honda BMS usable SOC window (% of true capacity)
FACTORY_SOC_MIN = 20           # Honda BMS floor -- never discharges below 20%
FACTORY_SOC_MAX = 80           # Honda BMS ceiling -- never charges above 80%
FACTORY_CELL_DELTA_V = 0.020   # New pack cell spread: <20mV between min/max cell
FACTORY_CELL_DELTA = 0.02      # Alias for backward compatibility
FACTORY_HEALTH = 100           # Perfect health score baseline

# Cell voltage thresholds (per-cell, not pack)
CELL_MIN_V = 2.5               # Absolute minimum (BMS hard cutoff)
CELL_MAX_V = 4.2               # Absolute maximum (BMS hard cutoff)
CELL_OPERATING_MIN_V = 3.0     # BMS soft low limit during normal use
CELL_OPERATING_MAX_V = 4.1     # BMS soft high limit during normal use

# Expected lifespan
EXPECTED_CYCLE_LIFE = (1000, 2000)  # Full cycles to 80% capacity (NMC cell-level)

# Operating temperature (Celsius)
NORMAL_TEMP_RANGE = (-30, 55)       # Blue Energy EHW rated range
OPTIMAL_TEMP_RANGE = (20, 30)       # Best performance / longevity window

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
        self.total_distance = 0  # miles driven this session
        self._last_speed_time = 0
        self.power_samples = []
        self.regen_count = 0
        self.total_samples = 0

        # Voltage tracking for health analysis
        self.voltage_history = []  # last 60 readings for delta calculation
        self.soc_history = []

        # Capacity estimation: track (soc, odometer) pairs for SOC%/mile
        self.soc_distance_pairs = []  # [(soc, distance_mi)]
        self.capacity_soc_per_mi = 0  # SOC% consumed per mile

        # Regen recovery tracking: measure how fast SOC recovers during regen
        self.regen_episodes = []  # [(duration_s, soc_gained)]
        self._regen_start_time = 0
        self._regen_start_soc = 0
        self._in_regen_episode = False
        self.regen_recovery_rate = 0  # SOC%/min during regen (higher = healthier)

        # Voltage stability: rolling standard deviation of pack voltage
        self.voltage_stability = 0  # lower = healthier

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

    def _replacement_hint(self, health_score, cell_delta):
        """Subtle replacement nudge based on health metrics.

        Returns None when healthy, or a quiet one-word hint:
          "Monitor" — keep an eye on it
          "Plan"    — start planning replacement
          "Soon"    — replacement recommended
        """
        # Worst-case tier wins (health OR cell_delta can trigger independently)
        if health_score < 30 or cell_delta > 0.3:
            return "Soon"
        if health_score < 50 or cell_delta > 0.2:
            return "Plan"
        if health_score < 70 or cell_delta > 0.1:
            return "Monitor"
        return None

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
            # OBD connected but no PIDs responding — car ignition likely off
            self.current_data.update({
                "connected": True,
                "soc": 0,
                "pack_voltage": 0,
                "health_score": 0,
                "power_kw": 0,
                "ignition": False,
            })
            return self.current_data

        now = time.time()

        # Extract what we can from standard PIDs
        # HYBRID_BATTERY_REMAINING (PID 015B) needs ignition ON to read
        soc = data.get("HYBRID_BATTERY_REMAINING", -1)
        voltage = data.get("CONTROL_MODULE_VOLTAGE", 0)  # 12V system

        # If HV SOC not available, estimate from 12V system voltage
        # 12V battery is charged by the HV system — its voltage correlates
        if soc < 0 or soc == 0:
            if voltage > 14.0:
                soc = 80  # engine running, alternator charging
            elif voltage > 13.0:
                soc = 60
            elif voltage > 12.5:
                soc = 40
            elif voltage > 12.0:
                soc = 20
            else:
                soc = 5  # very low
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

        # ── Capacity estimation: SOC% consumed per mile ──
        if speed > 1 and not is_regen:
            self.soc_distance_pairs.append((soc, self.total_distance))
            # Keep last 100 pairs, compute over at least 0.5 mi of driving
            self.soc_distance_pairs = self.soc_distance_pairs[-100:]
            if len(self.soc_distance_pairs) >= 10:
                s0, d0 = self.soc_distance_pairs[0]
                s1, d1 = self.soc_distance_pairs[-1]
                dist = d1 - d0
                if dist > 0.3:
                    self.capacity_soc_per_mi = abs(s0 - s1) / dist

        # ── Regen recovery tracking ──
        if is_regen and not self._in_regen_episode:
            # Starting a regen episode
            self._in_regen_episode = True
            self._regen_start_time = now
            self._regen_start_soc = soc
        elif not is_regen and self._in_regen_episode:
            # Ending a regen episode
            self._in_regen_episode = False
            regen_dur = now - self._regen_start_time
            regen_gain = soc - self._regen_start_soc
            if regen_dur > 3 and regen_gain > 0:
                self.regen_episodes.append((regen_dur, regen_gain))
                self.regen_episodes = self.regen_episodes[-20:]
                # Average SOC%/min gained during regen
                total_gain = sum(g for _, g in self.regen_episodes)
                total_dur = sum(d for d, _ in self.regen_episodes)
                if total_dur > 0:
                    self.regen_recovery_rate = (total_gain / total_dur) * 60

        # ── Voltage stability: std dev of recent voltage readings ──
        if len(self.voltage_history) > 5:
            v_vals = [v for _, v in self.voltage_history[-30:]]
            v_mean = sum(v_vals) / len(v_vals)
            v_variance = sum((v - v_mean) ** 2 for v in v_vals) / len(v_vals)
            self.voltage_stability = v_variance ** 0.5

        # ── Health score (0-100): multi-factor assessment ──
        # Start at 100, deduct for each risk factor with weighted penalties
        health = 100

        # Factor 1: Cell imbalance (cell_delta) — strongest indicator
        # 0.0-0.05V delta = healthy, >0.2V = failing
        if cell_delta > 0.05:
            health -= min(40, int((cell_delta - 0.05) * 200))

        # Factor 2: Voltage stability — erratic voltage = degraded cells
        # Std dev > 5V under normal driving is concerning
        if self.voltage_stability > 3:
            health -= min(20, int((self.voltage_stability - 3) * 5))

        # Factor 3: SOC recovery during regen — healthy pack recovers fast
        # Expect > 1 SOC%/min during active regen; below 0.3 is concerning
        if len(self.regen_episodes) >= 3:
            if self.regen_recovery_rate < 0.3:
                health -= 15
            elif self.regen_recovery_rate < 0.6:
                health -= 8

        # Factor 4: Capacity consumption — high SOC%/mi = reduced capacity
        # Typical healthy pack: ~1-3 SOC%/mi; >5 = pack is struggling
        if self.capacity_soc_per_mi > 5:
            health -= min(15, int((self.capacity_soc_per_mi - 5) * 5))
        elif self.capacity_soc_per_mi > 3.5:
            health -= 5

        # Factor 5: Rapid voltage swings = internal resistance increase
        if abs(discharge_rate) > 8:
            health -= min(10, int((abs(discharge_rate) - 8) * 2))

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

        # Distance accumulation for capacity tracking
        if speed > 1 and self._last_speed_time > 0:
            dt_hr = (now - self._last_speed_time) / 3600
            if dt_hr < 0.01:
                self.total_distance += speed * dt_hr
        self._last_speed_time = now

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
            "capacity_soc_per_mi": round(self.capacity_soc_per_mi, 2),
            "regen_recovery_rate": round(self.regen_recovery_rate, 2),
            "voltage_stability": round(self.voltage_stability, 2),
            "voltage_trend": [v for _, v in self.voltage_history[-30:]],
            "soc_trend": [s for _, s in self.soc_history[-30:]],
            # Factory reference values for widget comparison
            "factory_soc_min": FACTORY_SOC_MIN,
            "factory_soc_max": FACTORY_SOC_MAX,
            "factory_cell_delta": FACTORY_CELL_DELTA,
            "factory_health": FACTORY_HEALTH,
            # Subtle replacement hint — None when healthy
            "replacement_hint": self._replacement_hint(health, cell_delta),
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
