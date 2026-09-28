"""Turn a scan CSV into pictures of the shape.
A single-tilt-row scan instead gets the recommended 2D top-down plot.
"""
import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

from scanner_common import load_calibration, ray_dirs, raw_to_cm, read_scan_csv, to_xyz

VALID_CM = (15, 200)   # anything outside this is noise / no return


def otsu_threshold(values, bins=64):
    """Pick the depth that best separates two groups (shape vs wall)."""
    hist, edges = np.histogram(values, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist); w1 = w0[-1] - w0
    m0 = np.cumsum(hist * centers) / np.maximum(w0, 1)
    m1 = (np.sum(hist * centers) - np.cumsum(hist * centers)) / np.maximum(w1, 1)
    between = w0 * w1 * (m0 - m1) ** 2
    return float(centers[np.argmax(between)])


def load(path):
    cal = load_calibration()
    pan, tilt, raw = read_scan_csv(path)
    dist = raw_to_cm(raw, cal)
    valid = (dist > VALID_CM[0]) & (dist < VALID_CM[1])
    x, y, z = to_xyz(pan, tilt, dist)
    return dict(pan=pan, tilt=tilt, raw=raw, dist=dist, x=x, y=y, z=z, valid=valid)


def plot_row(s, title):
    """Single tilt row -> 2D top-down view (the 'recommended' sanity check)."""
    v = s["valid"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.8))
    a1.plot(s["pan"][v], s["dist"][v], "o-", ms=3, color="#2a6fdb")
    a1.set_xlabel("Pan servo angle (deg)"); a1.set_ylabel("Distance (cm)")
    a1.set_title("Distance vs pan angle"); a1.grid(alpha=0.3)
    a2.scatter(s["x"][v], s["z"][v], s=12, c=s["z"][v], cmap="viridis_r")
    a2.plot(0, 0, "r^", ms=10, label="scanner")
    a2.set_xlabel("x, left/right (cm)"); a2.set_ylabel("z, distance ahead (cm)")
    a2.set_title("Top-down view"); a2.set_aspect("equal"); a2.grid(alpha=0.3); a2.legend()
    fig.suptitle(title)
    return fig


def plot_full(s, title, threshold=None):
    v = s["valid"]
    x, y, z = s["x"][v], s["y"][v], s["z"][v]
    thr = threshold if threshold is not None else otsu_threshold(z)
    near = z < thr

    # marker size scaled to point spacing so the front view looks solid
    # Front views: put every scan point on a regular (pan, tilt) grid and project
    # each ray onto the plane of the shape, so the image is sized in real cm.
    plane = float(np.percentile(z[near], 20)) if near.any() else float(np.median(z))
    pans, tilts = np.unique(s["pan"]), np.unique(s["tilt"])
    Z = np.full((len(tilts), len(pans)), np.nan)
    zi = np.where(s["valid"], s["z"], np.nan)
    Z[np.searchsorted(tilts, s["tilt"]), np.searchsorted(pans, s["pan"])] = zi
    P, T = np.meshgrid(pans, tilts)
    ux, uy, uz = ray_dirs(P, T)
    GX, GY = plane * ux / uz, plane * uy / uz             # where each ray meets the shape plane

    fig = plt.figure(figsize=(13, 10))
    ax1 = fig.add_subplot(2, 2, 1)
    m = ax1.pcolormesh(GX, GY, Z, cmap="viridis_r", shading="nearest")
    fig.colorbar(m, ax=ax1, label="depth z (cm)")
    ax1.set_title("Front view, coloured by depth"); ax1.set_aspect("equal")
    ax1.set_xlabel(f"x on shape plane (cm, plane at {plane:.0f} cm)"); ax1.set_ylabel("y (cm)")

    ax2 = fig.add_subplot(2, 2, 2)
    mask = np.where(np.isnan(Z), np.nan, (Z < thr).astype(float))
    ax2.pcolormesh(GX, GY, mask, cmap=plt.matplotlib.colors.ListedColormap(["#e6e6e6", "#e0572b"]),
                   shading="nearest", vmin=0, vmax=1)
    ax2.set_title(f"Segmented: orange = shape (closer than {thr:.1f} cm)"); ax2.set_aspect("equal")
    ax2.set_xlabel("x on shape plane (cm)"); ax2.set_ylabel("y (cm)")

    ax3 = fig.add_subplot(2, 2, 3, projection="3d")
    ax3.scatter(x, z, y, c=z, cmap="viridis_r", s=4)
    ax3.scatter([0], [0], [0], c="red", marker="^", s=60)
    ax3.set_xlabel("x (cm)"); ax3.set_ylabel("z depth (cm)"); ax3.set_zlabel("y (cm)")
    ax3.set_title("3D point cloud (scanner = red)"); ax3.view_init(elev=15, azim=-70)

    ax4 = fig.add_subplot(2, 2, 4)
    ax4.hist(z, bins=60, color="#2a6fdb")
    ax4.axvline(thr, color="#e0572b", lw=2, label=f"threshold {thr:.1f} cm")
    ax4.set_xlabel("depth z (cm)"); ax4.set_ylabel("points"); ax4.legend()
    ax4.set_title("Depth histogram: left peak = shape, right peak = wall")

    fig.suptitle(title, fontsize=13)
    fig.tight_layout()
    n_shape = int(near.sum())
    print(f"{len(z)} valid points, {n_shape} on shape, {len(z)-n_shape} on wall, threshold {thr:.1f} cm")
    return fig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--threshold", type=float, help="depth (cm) splitting shape from wall; auto if omitted")
    ap.add_argument("--no-show", action="store_true")
    args = ap.parse_args()

    path = Path(args.csv)
    s = load(path)
    print(f"Loaded {len(s['raw'])} points ({(~s['valid']).sum()} out of range) from {path.name}")
    single_row = len(np.unique(s["tilt"])) == 1
    fig = plot_row(s, path.stem) if single_row else plot_full(s, path.stem, args.threshold)
    out = path.with_suffix(".png")
    fig.savefig(out, dpi=150)
    print(f"Saved {out}")
    if not args.no_show:
        plt.show()


if __name__ == "__main__":
    main()
