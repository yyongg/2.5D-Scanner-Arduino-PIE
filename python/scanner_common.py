"""Shared helpers: serial connection, calibration model, and geometry.

Edit the GEOMETRY section below to match YOUR mount after you build it.
"""
import json
import math
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
CALIBRATION_FILE = HERE / "calibration.json"

# ---------------------------------------------------------------------------
# GEOMETRY - measure these on your finished pan/tilt mount (in cm / degrees)
# ---------------------------------------------------------------------------
PAN_HOME = 90          # servo angle where the sensor points straight at the shape
TILT_HOME = 90         # servo angle where the sensor is level
PAN_SIGN = 1           # flip to -1 if increasing pan angle turns the sensor RIGHT->LEFT
TILT_SIGN = 1          # flip to -1 if increasing tilt angle points the sensor DOWN
SENSOR_FORWARD_OFFSET = 2.0   # cm from tilt axis to the sensor's front face, along the beam
TILT_AXIS_HEIGHT = 0.0        # cm the tilt axis sits above the pan axis
# The Sharp sensor measures from its lens face; the offsets turn that into a
# distance from the pan/tilt pivot so the trigonometry is exact.

# ---------------------------------------------------------------------------
# Serial
# ---------------------------------------------------------------------------
BAUD = 115200


def find_port():
    """Best guess at the Arduino's serial port."""
    from serial.tools import list_ports
    ports = list(list_ports.comports())
    for p in ports:
        desc = f"{p.description} {p.manufacturer or ''}".lower()
        if any(k in desc for k in ("arduino", "ch340", "usb serial", "usbmodem", "wch")):
            return p.device
    for p in ports:
        if "usbmodem" in p.device or "ttyACM" in p.device or "ttyUSB" in p.device:
            return p.device
    if ports:
        return ports[0].device
    raise SystemExit("No serial ports found - is the Arduino plugged in?")


def connect(port=None, timeout=2.0):
    """Open the port and wait for the sketch's READY banner (opening resets the Uno)."""
    import serial
    port = port or find_port()
    print(f"Connecting to {port} ...")
    ser = serial.Serial(port, BAUD, timeout=timeout)
    deadline = time.time() + 6
    while time.time() < deadline:
        line = ser.readline().decode(errors="ignore").strip()
        if line == "READY":
            print("Arduino ready.")
            return ser
        if not line:
            ser.write(b"P\n")
    raise SystemExit("Arduino never said READY - check the sketch is uploaded and the baud rate is 115200.")


def command(ser, text, expect_prefix=None):
    ser.write((text + "\n").encode())
    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            raise TimeoutError(f"No reply to '{text}'")
        if line.startswith("ERR"):
            raise RuntimeError(line)
        if expect_prefix is None or line.startswith(expect_prefix):
            return line


# ---------------------------------------------------------------------------
# Calibration:  distance_cm = a * raw ** b   (power law, fitted in log-log space)
# The GP2Y0A02YK0F output is roughly proportional to 1/distance over 20-150 cm,
# so b comes out near -1.  Readings closer than ~20 cm fold back and are invalid.
# ---------------------------------------------------------------------------
def fit_calibration(distances_cm, raws):
    d = np.asarray(distances_cm, float)
    r = np.asarray(raws, float)
    ok = (r > 0) & (d > 0)
    b, log_a = np.polyfit(np.log(r[ok]), np.log(d[ok]), 1)
    return {"model": "power", "a": float(math.exp(log_a)), "b": float(b),
            "raw_min": int(r[ok].min()), "raw_max": int(r[ok].max()),
            "d_min": float(d[ok].min()), "d_max": float(d[ok].max())}


def load_calibration(path=CALIBRATION_FILE):
    path = Path(path)
    if not path.exists():
        raise SystemExit(f"{path} not found - run calibrate.py first.")
    return json.loads(path.read_text())


def raw_to_cm(raw, cal):
    raw = np.asarray(raw, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        d = cal["a"] * np.power(np.clip(raw, 1, None), cal["b"])
    return d


def cm_to_raw(d, cal):
    """Inverse model (used by the simulator)."""
    return np.power(np.asarray(d, float) / cal["a"], 1.0 / cal["b"])


# ---------------------------------------------------------------------------
# Geometry: servo angles + distance -> x (right), y (up), z (forward, toward shape)
# ---------------------------------------------------------------------------
def ray_dirs(pan_servo, tilt_servo):
    """Unit vector the sensor points along for given servo angles."""
    pan = np.radians(PAN_SIGN * (np.asarray(pan_servo, float) - PAN_HOME))
    tilt = np.radians(TILT_SIGN * (np.asarray(tilt_servo, float) - TILT_HOME))
    return np.cos(tilt) * np.sin(pan), np.sin(tilt), np.cos(tilt) * np.cos(pan)


def to_xyz(pan_servo, tilt_servo, dist_cm):
    ux, uy, uz = ray_dirs(pan_servo, tilt_servo)
    r = np.asarray(dist_cm, float) + SENSOR_FORWARD_OFFSET
    return r * ux, TILT_AXIS_HEIGHT + r * uy, r * uz


def read_scan_csv(path):
    """Returns (pan, tilt, raw) arrays; ignores '#' metadata lines."""
    rows = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("pan"):
            continue
        p, t, r = line.split(",")[:3]
        rows.append((int(p), int(t), int(r)))
    if not rows:
        raise SystemExit(f"No data rows in {path}")
    a = np.array(rows)
    return a[:, 0], a[:, 1], a[:, 2]
