# MP2 Pan/Tilt IR Scanner

An Arduino UNO sweeps a Sharp GP2Y0A02YK0F IR sensor on two servos (pan and tilt).
It sends the readings to a laptop, and Python converts them into a picture of the shape.

```
arduino/pan_tilt_scanner/pan_tilt_scanner.ino   firmware: moves servos, reads sensor, answers serial commands
hardware_test/hardware_test.ino                 Serial Monitor test menu (local only, gitignored)
python/scanner_common.py                        shared settings, serial connection, calibration math, geometry
python/calibrate.py                             calibrate the sensor and check the calibration
python/scan.py                                  run a scan and save it to python/scans/<name>_<time>.csv
python/visualize.py                             turn a scan CSV into plots (PNG saved next to the CSV)
```

## Setup
1. In the Arduino IDE, upload `pan_tilt_scanner.ino` to the UNO. It uses the built-in **Servo** library.
2. Install the Python packages: `pip install pyserial numpy matplotlib`
3. **Close the Serial Monitor** before running any Python script. Otherwise you get "Access is denied" on the COM port.
   The port is set by `PORT = "COM9"` in `scanner_common.py`. To use a different one, add `--port COM5`.

## Workflow (run from `python/`)
1. **Calibrate:** `python calibrate.py`
   Place a flat target at about 8–10 distances between 20 and 150 cm from the sensor face, and type in each distance.
   This saves `calibration.json` and `calibration_fit.png`.
2. **Verify:** `python calibrate.py --verify`
   Use distances that you did *not* calibrate at.
3. **Single-row check:** `python scan.py --name row --tilt 95 95`
   This sweeps one row and gives a top-down plot.
4. **Full scan:** `python scan.py --name shape --pan 60 120 --tilt 88 115`
   A live map fills in as the scan runs. Start the tilt window above the table, or the bottom rows will just show the table. Add `--step 2` for a quick preview.
5. **Plot:** `python visualize.py scans/shape_<time>.csv`
   If the automatic split between shape and wall looks wrong, add `--threshold 60` (in cm).

## Settings
- `PAN_HOME` and `TILT_HOME` are the servo angles that point straight ahead and level. Set them in **both** `scanner_common.py` and `pan_tilt_scanner.ino`.
- `PAN_SIGN` and `TILT_SIGN` are in `scanner_common.py`. Change one to `-1` if the picture comes out mirrored or upside down.
- In `pan_tilt_scanner.ino`:
  - `SAMPLES` is the number of readings per point (the median is kept). Raise it if readings are noisy.
  - `SETTLE_MS` is how long to wait after each move. Raise it if rows look smeared.
  - Every row scans left to right, so all the rows line up.

## Serial commands (115200 baud, newline)
`P` ping · `G 90 90` move to pan/tilt · `R 15` median of 15 readings · `S 60 120 1 88 115 1` scan · `X` abort
