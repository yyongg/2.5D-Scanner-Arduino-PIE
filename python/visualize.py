"""Plot a scan.

  python visualize.py scans/smiley_20260928_120000.csv
  python visualize.py scans/smiley_20260928_120000.csv --threshold 60

A one-row scan gives a top-down view. A full scan gives a front view of the
shape. The plot is also saved as a PNG next to the CSV.
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

from scanner_common import (PAN_HOME, PAN_SIGN, TILT_HOME, TILT_SIGN,
                            load_calibration, raw_to_cm, read_scan, to_xyz)


def otsu(values):
    """Find the depth that best splits the points into two groups (shape and wall).
    It tries many cut-offs and keeps the one where the two groups are most separated."""
    best, best_score = values.min(), 0
    for cut in np.linspace(values.min(), values.max(), 200):
        near, far = values[values < cut], values[values >= cut]
        if len(near) and len(far):
            score = len(near) * len(far) * (near.mean() - far.mean()) ** 2
            if score > best_score:
                best, best_score = cut, score
    return best


def plot_row(pan, dist, x, z):
    """One row: distance vs angle, and a top-down map."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    ax1.plot(pan, dist, "o-")
    ax1.set(xlabel="pan servo angle (deg)", ylabel="distance (cm)", title="Distance vs pan angle")
    ax2.scatter(x, z, s=10)
    ax2.plot(0, 0, "r^", label="scanner")
    ax2.set(xlabel="x (cm)", ylabel="z, distance ahead (cm)", title="Top-down view")
    ax2.set_aspect("equal")
    ax2.legend()
    return fig


def plot_full(pan, tilt, z, threshold):
    """Full scan: front view coloured by depth, shape/wall split, and histogram."""
    # Arrange depths into a grid: one row per tilt angle, one column per pan angle
    pans, tilts = np.unique(pan), np.unique(tilt)
    grid = np.full((len(tilts), len(pans)), np.nan)
    grid[np.searchsorted(tilts, tilt), np.searchsorted(pans, pan)] = z
    if PAN_SIGN < 0:
        grid = grid[:, ::-1]
    if TILT_SIGN < 0:
        grid = grid[::-1, :]

    # Convert the angle range to cm on the shape (distance * tan(angle))
    shape_dist = np.nanmedian(z[z < threshold])
    x_cm = shape_dist * np.tan(np.radians(np.sort(PAN_SIGN * (pans - PAN_HOME))))
    y_cm = shape_dist * np.tan(np.radians(np.sort(TILT_SIGN * (tilts - TILT_HOME))))
    extent = [x_cm[0], x_cm[-1], y_cm[0], y_cm[-1]]

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(17, 5))
    img = ax1.imshow(grid, origin="lower", extent=extent, cmap="viridis_r")
    fig.colorbar(img, ax=ax1, label="depth (cm)")
    ax1.set(xlabel="x (cm)", ylabel="y (cm)", title="Front view, coloured by depth")

    is_shape = np.where(np.isnan(grid), np.nan, grid < threshold)
    gray_orange = ListedColormap(["lightgray", "orangered"])   # wall = gray, shape = orange
    ax2.imshow(is_shape, origin="lower", extent=extent, cmap=gray_orange, vmin=0, vmax=1)
    ax2.set(xlabel="x (cm)", ylabel="y (cm)", title=f"Shape = closer than {threshold:.0f} cm")

    ax3.hist(z[~np.isnan(z)], bins=50)
    ax3.axvline(threshold, color="r", label=f"threshold {threshold:.0f} cm")
    ax3.set(xlabel="depth (cm)", ylabel="points", title="Depths: shape peak and wall peak")
    ax3.legend()
    return fig


ap = argparse.ArgumentParser()
ap.add_argument("csv")
ap.add_argument("--threshold", type=float, help="depth in cm that splits shape from wall")
args = ap.parse_args()

pan, tilt, raw = read_scan(args.csv)
dist = raw_to_cm(raw, load_calibration())
dist[(dist < 20) | (dist > 150)] = np.nan   # sensor only works from 20 to 150 cm
x, y, z = to_xyz(pan, tilt, dist)

if len(np.unique(tilt)) == 1:
    fig = plot_row(pan, dist, x, z)
else:
    valid_z = z[~np.isnan(z)]
    threshold = args.threshold or otsu(valid_z)
    fig = plot_full(pan, tilt, z, threshold)

fig.suptitle(Path(args.csv).stem)
fig.tight_layout()
fig.savefig(Path(args.csv).with_suffix(".png"), dpi=150)
plt.show()
