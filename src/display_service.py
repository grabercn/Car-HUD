#!/usr/bin/env python3
"""Car-HUD Display Service
Controls TFT backlight brightness via PWM on GPIO 18.
Future: BH1750 lux sensor for auto-brightness.

PWM wiring: Display PWM pin → GPIO 18 (pin 12), GND → any GND pin.
"""

import os
import sys
import json
import time
import signal

SIGNAL_FILE = "/tmp/car-hud-display-data"
BRIGHTNESS_FILE = "/home/chrismslist/car-hud/.brightness"
LOG_FILE = "/tmp/car-hud-display.log"

PWM_PIN = 18        # GPIO 18 = hardware PWM0 (pin 12)
PWM_FREQ = 1000     # 1kHz PWM frequency
DEFAULT_BRIGHTNESS = 80  # 0-100%

# Future: BH1750 lux sensor
LUX_ENABLED = False
# LUX_I2C_ADDR = 0x23


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


def load_brightness():
    """Load saved brightness level."""
    try:
        with open(BRIGHTNESS_FILE) as f:
            d = json.load(f)
            return max(0, min(100, d.get("brightness", DEFAULT_BRIGHTNESS)))
    except Exception:
        return DEFAULT_BRIGHTNESS


def save_brightness(level):
    """Save brightness level."""
    try:
        with open(BRIGHTNESS_FILE, "w") as f:
            json.dump({"brightness": level}, f)
    except Exception:
        pass


class DisplayController:
    def __init__(self):
        self.pwm = None
        self.brightness = DEFAULT_BRIGHTNESS
        self.auto_mode = True
        self.lux = 0

    def setup_pwm(self):
        """Initialize hardware PWM on GPIO 18."""
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(PWM_PIN, GPIO.OUT)
            self.pwm = GPIO.PWM(PWM_PIN, PWM_FREQ)
            self.pwm.start(self.brightness)
            log(f"PWM initialized on GPIO {PWM_PIN} at {self.brightness}%")
            return True
        except ImportError:
            log("RPi.GPIO not available — trying gpiozero")
            try:
                from gpiozero import PWMLED
                self.pwm_led = PWMLED(PWM_PIN)
                self.pwm_led.value = self.brightness / 100
                log(f"gpiozero PWM on GPIO {PWM_PIN} at {self.brightness}%")
                return True
            except Exception as e:
                log(f"gpiozero failed: {e}")
        except Exception as e:
            log(f"PWM setup failed: {e}")
            # Fallback: try sysfs PWM
            try:
                self._setup_sysfs_pwm()
                return True
            except Exception as e2:
                log(f"sysfs PWM also failed: {e2}")
        return False

    def _setup_sysfs_pwm(self):
        """Fallback: use sysfs PWM interface."""
        pwm_path = "/sys/class/pwm/pwmchip0"
        if not os.path.exists(pwm_path):
            raise Exception("No PWM chip found")

        # Export PWM channel 0 (GPIO 18)
        export_path = f"{pwm_path}/export"
        if not os.path.exists(f"{pwm_path}/pwm0"):
            with open(export_path, "w") as f:
                f.write("0")
            time.sleep(0.1)

        # Set period (1ms = 1000Hz)
        with open(f"{pwm_path}/pwm0/period", "w") as f:
            f.write("1000000")  # nanoseconds

        # Set duty cycle
        duty = int(self.brightness / 100 * 1000000)
        with open(f"{pwm_path}/pwm0/duty_cycle", "w") as f:
            f.write(str(duty))

        # Enable
        with open(f"{pwm_path}/pwm0/enable", "w") as f:
            f.write("1")

        log(f"sysfs PWM enabled at {self.brightness}%")
        self.pwm = "sysfs"

    def set_brightness(self, level):
        """Set brightness 0-100%."""
        level = max(0, min(100, int(level)))
        self.brightness = level

        if self.pwm == "sysfs":
            try:
                duty = int(level / 100 * 1000000)
                with open("/sys/class/pwm/pwmchip0/pwm0/duty_cycle", "w") as f:
                    f.write(str(duty))
            except Exception:
                pass
        elif self.pwm:
            try:
                self.pwm.ChangeDutyCycle(level)
            except AttributeError:
                # gpiozero
                try:
                    self.pwm_led.value = level / 100
                except Exception:
                    pass

        log(f"Brightness: {level}%")
        save_brightness(level)

    def read_lux(self):
        """Read ambient light from BH1750 sensor (future)."""
        if not LUX_ENABLED:
            return -1
        try:
            import smbus2
            bus = smbus2.SMBus(1)
            # BH1750 one-shot high-res mode
            bus.write_byte(0x23, 0x20)
            time.sleep(0.2)
            data = bus.read_i2c_block_data(0x23, 0x20, 2)
            lux = (data[0] << 8 | data[1]) / 1.2
            return lux
        except Exception:
            return -1

    def auto_brightness(self, lux):
        """Calculate brightness from lux reading."""
        if lux < 0:
            return self.brightness  # no sensor, keep current

        # Map lux to brightness: 0 lux = 10%, 1000+ lux = 100%
        if lux < 10:
            return 10
        elif lux < 50:
            return 30
        elif lux < 200:
            return 50
        elif lux < 500:
            return 70
        elif lux < 1000:
            return 85
        else:
            return 100

    def check_commands(self):
        """Check for brightness commands from voice/web."""
        try:
            with open("/tmp/car-hud-voice-signal") as f:
                sig = json.load(f)
            if time.time() - sig.get("time", 0) < 5:
                action = sig.get("action", "")
                target = sig.get("target", "")
                if action == "brightness":
                    if target == "up":
                        self.set_brightness(min(100, self.brightness + 20))
                    elif target == "down":
                        self.set_brightness(max(5, self.brightness - 20))
                    elif target == "max":
                        self.set_brightness(100)
                    elif target == "min":
                        self.set_brightness(10)
                    elif target == "auto":
                        self.auto_mode = True
                        log("Auto brightness enabled")
        except Exception:
            pass

    def run(self):
        self.brightness = load_brightness()

        if not self.setup_pwm():
            log("No PWM available — running in monitor-only mode")

        log(f"Display service running (brightness={self.brightness}%)")

        while True:
            # Check voice/web commands
            self.check_commands()

            # Auto brightness from lux sensor
            if self.auto_mode and LUX_ENABLED:
                self.lux = self.read_lux()
                if self.lux >= 0:
                    target = self.auto_brightness(self.lux)
                    # Smooth transition
                    if abs(target - self.brightness) > 5:
                        step = 2 if target > self.brightness else -2
                        self.set_brightness(self.brightness + step)

            # Publish state
            write_data({
                "brightness": self.brightness,
                "auto_mode": self.auto_mode,
                "lux": self.lux,
                "lux_enabled": LUX_ENABLED,
                "pwm_pin": PWM_PIN,
            })

            time.sleep(1)


def main():
    log("Display service starting...")
    ctrl = DisplayController()

    def cleanup(signum, frame):
        log("Shutting down...")
        if ctrl.pwm and ctrl.pwm != "sysfs":
            try:
                ctrl.pwm.stop()
            except Exception:
                pass
        try:
            import RPi.GPIO as GPIO
            GPIO.cleanup(PWM_PIN)
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)
    ctrl.run()


if __name__ == "__main__":
    main()
