"""Calibrate the IR sensor.

  python calibrate.py            measure known distances and fit a curve
  python calibrate.py --verify   check the fit at NEW distances

Point the sensor at a flat target, type the distance from the sensor face in cm,
press Enter. Repeat for about 8-10 distances between 20 and 150 cm.
Press Enter on an empty line to finish.
"""
import argparse
import csv
import json

import numpy as np
import matplotlib.pyplot as plt

from scanner_common import (CALIBRATION_FILE, HERE, PAN_HOME, TILT_HOME,
                            command, connect, load_calibration, raw_to_cm)


def measure(ser):
    """Ask for distances and read the sensor at each one."""
    points = []
    while True:
        text = input("distance in cm (Enter to finish): ").strip()
        if not text:
            return points
        raw = int(command(ser, "R 25").split()[1])   # median of 25 readings
        print(f"  raw = {raw}")
        points.append((float(text), raw))


def calibrate(ser):
    points = measure(ser)
    d = np.array([p[0] for p in points])
    raw = np.array([p[1] for p in points])

    # Fit a straight line in log-log space: log(d) = b*log(raw) + log(a)
    b, log_a = np.polyfit(np.log(raw), np.log(d), 1)
    cal = {"a": float(np.exp(log_a)), "b": float(b)}
    CALIBRATION_FILE.write_text(json.dumps(cal, indent=2))
    print(f"distance = {cal['a']:.0f} * raw^{b:.3f}   (saved to calibration.json)")

    with open(HERE / "calibration_points.csv", "w", newline="") as f:
        csv.writer(f).writerows([("distance_cm", "raw")] + points)

    curve = np.linspace(raw.min(), raw.max(), 200)
    plt.scatter(raw, d, label="measured")
    plt.plot(curve, raw_to_cm(curve, cal), "r", label="fit")
    plt.xlabel("raw reading (0-1023)")
    plt.ylabel("distance (cm)")
    plt.title("IR sensor calibration")
    plt.legend()
    plt.savefig(HERE / "calibration_fit.png", dpi=150)
    plt.show()


def verify(ser):
    cal = load_calibration()
    rows = [("actual_cm", "raw", "predicted_cm", "error_cm")]
    while True:
        text = input("actual distance in cm (Enter to finish): ").strip()
        if not text:
            break
        actual = float(text)
        raw = int(command(ser, "R 25").split()[1])
        predicted = float(raw_to_cm(raw, cal))
        print(f"  predicted {predicted:.1f} cm, error {predicted - actual:+.1f} cm")
        rows.append((actual, raw, round(predicted, 1), round(predicted - actual, 1)))

    with open(HERE / "calibration_verify.csv", "w", newline="") as f:
        csv.writer(f).writerows(rows)
    print("Saved calibration_verify.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--port")
    args = ap.parse_args()

    ser = connect(args.port)
    command(ser, f"G {PAN_HOME} {TILT_HOME}")   # point straight ahead
    verify(ser) if args.verify else calibrate(ser)
