"""Calibrate the Sharp IR sensor, then verify the fit on new distances.

Usage:
    python calibrate.py                 # collect calibration points + fit
    python calibrate.py --verify        # test the saved fit at NEW distances
    python calibrate.py --fit-only      # refit from calibration_points.csv (no Arduino needed)

Procedure: point the sensor (servos at home) at a flat, matte target (a sheet
of cardboard works). Place it at a measured distance from the SENSOR FACE,
type that distance, press Enter; repeat every 10 cm from 20 to 150 cm.
"""
import argparse
import csv
import json

import numpy as np
import matplotlib.pyplot as plt

from scanner_common import (CALIBRATION_FILE, HERE, command, connect,
                            fit_calibration, load_calibration, raw_to_cm)

POINTS_FILE = HERE / "calibration_points.csv"
SAMPLES = 25   # ~1 s of readings per distance, median taken on the Arduino


def read_raw(ser):
    return int(command(ser, f"R {SAMPLES}", "RAW").split()[1])


def collect(ser):
    pts = []
    print("\nEnter the distance in cm (blank line to finish).")
    while True:
        s = input("distance cm> ").strip()
        if not s:
            break
        try:
            d = float(s)
        except ValueError:
            print("  not a number"); continue
        raw = read_raw(ser)
        print(f"  raw = {raw}")
        pts.append((d, raw))
    return pts


def save_points(pts):
    with open(POINTS_FILE, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["distance_cm", "raw"])
        w.writerows(pts)
    print(f"Saved {len(pts)} points to {POINTS_FILE.name}")


def load_points():
    with open(POINTS_FILE) as f:
        r = csv.DictReader(f)
        return [(float(row["distance_cm"]), int(row["raw"])) for row in r]


def fit_and_plot(pts):
    d = np.array([p[0] for p in pts]); raw = np.array([p[1] for p in pts])
    valid = d >= 20   # below ~20 cm the sensor output folds back - exclude
    cal = fit_calibration(d[valid], raw[valid])
    CALIBRATION_FILE.write_text(json.dumps(cal, indent=2))
    pred = raw_to_cm(raw[valid], cal)
    rmse = float(np.sqrt(np.mean((pred - d[valid]) ** 2)))
    print(f"\nFit: distance_cm = {cal['a']:.1f} * raw^{cal['b']:.3f}   (RMSE {rmse:.2f} cm)")
    print(f"Saved to {CALIBRATION_FILE.name}")

    rr = np.linspace(raw[valid].min() * 0.9, raw[valid].max() * 1.05, 200)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.scatter(raw[valid], d[valid], color="#2a6fdb", label="calibration points", zorder=3)
    if (~valid).any():
        ax.scatter(raw[~valid], d[~valid], color="#999", marker="x", label="excluded (<20 cm)")
    ax.plot(rr, raw_to_cm(rr, cal), color="#e0572b", label=f"fit: {cal['a']:.0f}·raw^{cal['b']:.2f}")
    ax.set_xlabel("Raw analog reading (0-1023)"); ax.set_ylabel("Distance (cm)")
    ax.set_title(f"IR sensor calibration  (RMSE {rmse:.2f} cm)")
    ax.grid(alpha=0.3); ax.legend()
    fig.tight_layout(); fig.savefig(HERE / "calibration_fit.png", dpi=150)
    print("Plot saved to calibration_fit.png")
    plt.show()


def verify(ser):
    cal = load_calibration()
    rows = []
    print("\nVERIFY: use distances you did NOT calibrate at (e.g. 25, 45, 75, 115 cm).")
    while True:
        s = input("actual distance cm> ").strip()
        if not s:
            break
        actual = float(s)
        raw = read_raw(ser)
        pred = float(raw_to_cm(raw, cal))
        err = pred - actual
        rows.append((actual, raw, pred, err))
        print(f"  raw {raw} -> predicted {pred:.1f} cm   error {err:+.1f} cm ({100*err/actual:+.1f}%)")
    if rows:
        errs = np.array([r[3] for r in rows])
        print(f"\nMean abs error {np.mean(np.abs(errs)):.2f} cm, max {np.max(np.abs(errs)):.2f} cm")
        with open(HERE / "calibration_verify.csv", "w", newline="") as f:
            w = csv.writer(f); w.writerow(["actual_cm", "raw", "predicted_cm", "error_cm"]); w.writerows(rows)
        print("Saved calibration_verify.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--fit-only", action="store_true")
    args = ap.parse_args()

    if args.fit_only:
        fit_and_plot(load_points())
    else:
        ser = connect(args.port)
        command(ser, "G 90 90", "OK")
        if args.verify:
            verify(ser)
        else:
            pts = collect(ser)
            if len(pts) < 4:
                raise SystemExit("Need at least 4 points for a sensible fit.")
            save_points(pts)
            fit_and_plot(pts)
        ser.close()
