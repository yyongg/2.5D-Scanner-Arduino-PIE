"""Settings and helpers shared by calibrate.py, scan.py and visualize.py."""
import json
from pathlib import Path

import numpy as np
import serial

HERE = Path(__file__).parent
CALIBRATION_FILE = HERE / "calibration.json"

PORT = "COM9"   # Arduino's serial port (override with --port)

# Servo angles that point straight ahead and level (must match the .ino)
PAN_HOME = 90
TILT_HOME = 90
# Change to -1 if the picture comes out mirrored (pan) or upside down (tilt)
PAN_SIGN = 1
TILT_SIGN = 1


def connect(port=None):
    """Open the serial port and wait for the Arduino to say READY."""
    ser = serial.Serial(port or PORT, 115200, timeout=2)
    # Opening the port restarts the Arduino, so wait for it to boot
    for _ in range(5):
        if ser.readline().decode().strip() == "READY":
            return ser
        ser.write(b"P\n")
    raise SystemExit("Arduino did not reply. Is the sketch uploaded and the Serial Monitor closed?")


def command(ser, text):
    """Send one command and return the Arduino's reply."""
    ser.write((text + "\n").encode())
    return ser.readline().decode().strip()


def load_calibration():
    if not CALIBRATION_FILE.exists():
        raise SystemExit("No calibration.json yet. Run calibrate.py first.")
    return json.loads(CALIBRATION_FILE.read_text())


def raw_to_cm(raw, cal):
    """Calibration curve: distance = a * raw^b"""
    raw = np.clip(np.asarray(raw, float), 1, None)   # avoid dividing by zero
    return cal["a"] * raw ** cal["b"]


def to_xyz(pan, tilt, dist):
    """Servo angles + distance -> x (right), y (up), z (straight ahead), in cm."""
    p = np.radians(PAN_SIGN * (np.asarray(pan) - PAN_HOME))
    t = np.radians(TILT_SIGN * (np.asarray(tilt) - TILT_HOME))
    x = dist * np.cos(t) * np.sin(p)
    y = dist * np.sin(t)
    z = dist * np.cos(t) * np.cos(p)
    return x, y, z


def read_scan(path):
    """Read a scan CSV. Returns pan, tilt, raw arrays."""
    rows = [line for line in open(path) if line[0].isdigit()]   # skip header lines
    data = np.loadtxt(rows, delimiter=",", dtype=int)
    return data[:, 0], data[:, 1], data[:, 2]
