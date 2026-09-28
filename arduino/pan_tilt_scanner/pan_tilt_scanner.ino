/*
  MP2 Pan/Tilt IR Scanner - Arduino firmware
  -------------------------------------------
  Hardware:
    Pan servo signal  -> D9
    Tilt servo signal -> D10
    Sharp GP2Y0A02YK0F Vo -> A0
    (see schematic for power wiring)

  Serial protocol (115200 baud, newline-terminated commands):
    P                         ping, replies "READY"
    G <pan> <tilt>            go to servo angles (degrees, 0-180), replies "OK <pan> <tilt>"
    R <n>                     take n samples at current position, replies "RAW <median>"
    S <p0> <p1> <ps> <t0> <t1> <ts>
                              raster scan pan p0..p1 step ps, tilt t0..t1 step ts
                              replies "# BEGIN", then one "pan,tilt,raw" line per point,
                              then "# END" (or "# ABORTED" if you send 'X' mid-scan)

  All angles are raw servo angles (90 = centre). The Python side converts them
  to physical angles relative to straight ahead.
*/

#include <Servo.h>

// ---------------- Pins ----------------
const uint8_t PAN_PIN    = 9;
const uint8_t TILT_PIN   = 10;
const uint8_t SENSOR_PIN = A0;

// ---------------- Tuning ----------------
const int PAN_HOME        = 90;   // servo angle that points straight at the shape
const int TILT_HOME       = 90;   // servo angle that points level
const int SETTLE_MS       = 60;   // wait after a small (1-2 deg) move
const int BIG_MOVE_MS     = 500;  // wait after a large move (row change, GOTO)
const int SAMPLES_PER_PT  = 5;    // readings per scan point (median taken)
const int SAMPLE_GAP_MS   = 40;   // sensor only updates every ~38 ms, so don't sample faster
const int MAX_SAMPLES     = 31;
// false = every row scans left->right (jump back to the row start between rows).
// The snake pattern gave inconsistent right->left rows, so it is off by default.
const bool SNAKE          = false;

// Safety limits so a bad command can't drive the mount into itself
const int PAN_MIN = 0,  PAN_MAX = 180;
const int TILT_MIN = 30, TILT_MAX = 150;

Servo panServo;
Servo tiltServo;
int curPan  = PAN_HOME;
int curTilt = TILT_HOME;

// ---------------------------------------------------------------------------
void moveTo(int pan, int tilt) {
  pan  = constrain(pan,  PAN_MIN,  PAN_MAX);
  tilt = constrain(tilt, TILT_MIN, TILT_MAX);
  int delta = max(abs(pan - curPan), abs(tilt - curTilt));
  panServo.write(pan);
  tiltServo.write(tilt);
  curPan  = pan;
  curTilt = tilt;
  delay(delta > 3 ? BIG_MOVE_MS : SETTLE_MS);
}

// Median of n analog readings - rejects the occasional spike much better than a mean
int readSensorMedian(int n) {
  static int buf[MAX_SAMPLES];
  n = constrain(n, 1, MAX_SAMPLES);
  for (int i = 0; i < n; i++) {
    buf[i] = analogRead(SENSOR_PIN);
    if (i < n - 1) delay(SAMPLE_GAP_MS);
  }
  // insertion sort (n is tiny)
  for (int i = 1; i < n; i++) {
    int key = buf[i], j = i - 1;
    while (j >= 0 && buf[j] > key) { buf[j + 1] = buf[j]; j--; }
    buf[j + 1] = key;
  }
  return buf[n / 2];
}

bool abortRequested() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'X' || c == 'x') return true;
  }
  return false;
}

// Raster scan. With SNAKE the pan direction alternates each row; without it,
// every row runs p0 -> p1 so all rows share the same servo approach direction.
void runScan(int p0, int p1, int ps, int t0, int t1, int ts) {
  if (ps <= 0) ps = 1;
  if (ts <= 0) ts = 1;
  if (p0 > p1) { int tmp = p0; p0 = p1; p1 = tmp; }
  if (t0 > t1) { int tmp = t0; t0 = t1; t1 = tmp; }

  Serial.println(F("# BEGIN"));
  Serial.println(F("pan,tilt,raw"));
  bool forward = true;
  for (int t = t0; t <= t1; t += ts) {
    int start = forward ? p0 : p1;
    int step  = forward ? ps : -ps;
    for (int p = start; forward ? (p <= p1) : (p >= p0); p += step) {
      if (abortRequested()) { Serial.println(F("# ABORTED")); moveTo(PAN_HOME, TILT_HOME); return; }
      moveTo(p, t);
      int raw = readSensorMedian(SAMPLES_PER_PT);
      Serial.print(p); Serial.print(',');
      Serial.print(t); Serial.print(',');
      Serial.println(raw);
    }
    if (SNAKE) forward = !forward;
  }
  Serial.println(F("# END"));
  moveTo(PAN_HOME, TILT_HOME);
}

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  panServo.attach(PAN_PIN);
  tiltServo.attach(TILT_PIN);
  panServo.write(PAN_HOME);
  tiltServo.write(TILT_HOME);
  delay(BIG_MOVE_MS);
  Serial.println(F("READY"));
}

void loop() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;

  char cmd = toupper(line.charAt(0));
  const char *args = line.c_str() + 1;
  int a, b, c, d, e, f;

  switch (cmd) {
    case 'P':
      Serial.println(F("READY"));
      break;

    case 'G':
      if (sscanf(args, "%d %d", &a, &b) == 2) {
        moveTo(a, b);
        Serial.print(F("OK ")); Serial.print(curPan); Serial.print(' '); Serial.println(curTilt);
      } else Serial.println(F("ERR usage: G <pan> <tilt>"));
      break;

    case 'R':
      if (sscanf(args, "%d", &a) != 1) a = 15;
      Serial.print(F("RAW ")); Serial.println(readSensorMedian(a));
      break;

    case 'S':
      if (sscanf(args, "%d %d %d %d %d %d", &a, &b, &c, &d, &e, &f) == 6) runScan(a, b, c, d, e, f);
      else Serial.println(F("ERR usage: S <p0> <p1> <pstep> <t0> <t1> <tstep>"));
      break;

    default:
      Serial.println(F("ERR unknown command"));
  }
}
