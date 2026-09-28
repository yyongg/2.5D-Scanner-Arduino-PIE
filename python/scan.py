"""Run a pan/tilt scan and save the raw data to CSV.

Angles are SERVO angles (90 = straight ahead). With the letter ~50 cm away, a
1 ft (30 cm) letter spans roughly +/-17 deg, so the default window adds margin
around that to see the wall on every side.
Press Ctrl+C to abort a scan cleanly.
"""
import argparse
import datetime as dt
import time
from pathlib import Path

from scanner_common import HERE, command, connect

SCANS_DIR = HERE / "scans"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    ap.add_argument("--name", default="scan")
    ap.add_argument("--pan", nargs=2, type=int, default=[68, 112], metavar=("MIN", "MAX"))
    ap.add_argument("--tilt", nargs=2, type=int, default=[70, 110], metavar=("MIN", "MAX"))
    ap.add_argument("--step", type=int, default=1, help="pan step in degrees")
    ap.add_argument("--tilt-step", type=int, default=None, help="defaults to --step")
    ap.add_argument("--note", default="", help="free-text note saved in the file header")
    args = ap.parse_args()
    ts = args.tilt_step or args.step

    (p0, p1), (t0, t1) = args.pan, args.tilt
    n_pts = ((p1 - p0) // args.step + 1) * ((t1 - t0) // ts + 1)
    print(f"Scanning pan {p0}-{p1}, tilt {t0}-{t1}, step {args.step}/{ts}: {n_pts} points "
          f"(~{n_pts * 0.23 / 60:.1f} min)")

    SCANS_DIR.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = SCANS_DIR / f"{args.name}_{stamp}.csv"

    ser = connect(args.port, timeout=5)
    ser.write(f"S {p0} {p1} {args.step} {t0} {t1} {ts}\n".encode())

    got, start = 0, time.time()
    with open(out, "w") as f:
        f.write(f"# scan {stamp} pan {p0}-{p1} tilt {t0}-{t1} step {args.step}/{ts} note: {args.note}\n")
        try:
            while True:
                line = ser.readline().decode(errors="ignore").strip()
                if not line:
                    continue
                if line.startswith("ERR"):
                    raise SystemExit(line)
                if line in ("# END", "# ABORTED"):
                    print(f"\n{line[2:]}")
                    break
                if line.startswith("#"):
                    continue
                f.write(line + "\n")
                if line[0].isdigit():
                    got += 1
                    f.flush()
                    el = time.time() - start
                    eta = el / got * (n_pts - got)
                    print(f"\r  {got}/{n_pts} points  ({100*got/n_pts:.0f}%)  ETA {eta:4.0f}s  last: {line}   ",
                          end="", flush=True)
        except KeyboardInterrupt:
            print("\nAborting ...")
            ser.write(b"X")
            time.sleep(1)
    ser.close()
    print(f"Saved {got} points to {out}")
    print(f"Next:  python visualize.py {out}")


if __name__ == "__main__":
    main()
