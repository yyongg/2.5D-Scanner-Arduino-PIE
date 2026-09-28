"""Run a scan and save it to scans/<name>_<time>.csv

  python scan.py --name smiley --pan 60 120 --tilt 88 115
  python scan.py --name row --tilt 95 95          (one row only)

Angles are servo angles. A live map fills in as the scan runs.
Press Ctrl+C to stop early.
"""
import argparse
import time

import numpy as np
import matplotlib.pyplot as plt

from scanner_common import HERE, PAN_SIGN, TILT_SIGN, connect, load_calibration, raw_to_cm

ap = argparse.ArgumentParser()
ap.add_argument("--name", default="scan")
ap.add_argument("--pan", nargs=2, type=int, default=[60, 120])
ap.add_argument("--tilt", nargs=2, type=int, default=[80, 110])
ap.add_argument("--step", type=int, default=1, help="degrees between points")
ap.add_argument("--port")
args = ap.parse_args()

(p0, p1), (t0, t1), step = args.pan, args.tilt, args.step
out = HERE / "scans" / f"{args.name}_{time.strftime('%Y%m%d_%H%M%S')}.csv"
out.parent.mkdir(exist_ok=True)
cal = load_calibration()

# Live map: one pixel per point (rows = tilt, columns = pan), coloured by distance
grid = np.full(((t1 - t0) // step + 1, (p1 - p0) // step + 1), np.nan)
plt.ion()
fig, ax = plt.subplots()
img = ax.imshow(grid, origin="lower", cmap="viridis_r", aspect="auto",
                extent=[p0 - step / 2, p1 + step / 2, t0 - step / 2, t1 + step / 2])
fig.colorbar(img, label="distance (cm)")
ax.set(xlabel="pan servo angle (deg)", ylabel="tilt servo angle (deg)", title=f"Live: {args.name}")
if PAN_SIGN < 0:
    ax.invert_xaxis()
if TILT_SIGN < 0:
    ax.invert_yaxis()
plt.pause(0.1)

ser = connect(args.port)
ser.write(f"S {p0} {p1} {step} {t0} {t1} {step}\n".encode())

count = 0
with open(out, "w") as f:
    try:
        while True:
            line = ser.readline().decode().strip()
            if line in ("# END", "# ABORTED"):
                break
            if not line or line.startswith("#"):
                continue
            f.write(line + "\n")   # data or column names
            if not line[0].isdigit():
                continue
            count += 1
            print(f"\r{count} points, last: {line}   ", end="")

            # Colour in this point on the live map
            p, t, raw = map(int, line.split(","))
            d = float(raw_to_cm(raw, cal))
            if 20 <= d <= 150:   # sensor only works from 20 to 150 cm
                grid[(t - t0) // step, (p - p0) // step] = d
                img.set_data(grid)
                img.set_clim(np.nanmin(grid), np.nanmax(grid))
            plt.pause(0.001)   # let the window redraw
    except KeyboardInterrupt:
        ser.write(b"X")   # tell the Arduino to stop

print(f"\nSaved {out}")
print(f"Next: python visualize.py {out}")
plt.ioff()
plt.show()   # keep the map open until you close it
