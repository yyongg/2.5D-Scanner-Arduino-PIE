/*
  Pan/tilt IR scanner.
  Pan servo -> pin 9, tilt servo -> pin 10, IR sensor -> A0.

  Commands (115200 baud, one per line):
    P                    -> READY
    G pan tilt           move servos          -> OK pan tilt
    R n                  median of n readings -> RAW value
    S p0 p1 ps t0 t1 ts  scan, one "pan,tilt,raw" line per point (send X to stop)
*/

#include <Servo.h>

const int PAN_HOME = 90;     // points straight ahead
const int TILT_HOME = 90;    // points level
const int SETTLE_MS = 60;    // wait after a 1-degree step
const int BIG_MOVE_MS = 500; // wait after a big jump (e.g. start of a row)
const int SAMPLES = 5;       // readings per scan point

Servo panServo, tiltServo;
int curPan = PAN_HOME, curTilt = TILT_HOME;

// Move both servos, then wait for them to stop moving.
void moveTo(int pan, int tilt) {
  pan = constrain(pan, 0, 180);
  tilt = constrain(tilt, 30, 150);  // keep the sensor from hitting the mount
  bool bigMove = abs(pan - curPan) > 3 || abs(tilt - curTilt) > 3;
  panServo.write(pan);
  tiltServo.write(tilt);
  curPan = pan;
  curTilt = tilt;
  delay(bigMove ? BIG_MOVE_MS : SETTLE_MS);
}

// Take n readings and return the middle one (ignores random spikes).
int readSensor(int n) {
  int r[31];
  n = constrain(n, 1, 31);
  for (int i = 0; i < n; i++) {
    r[i] = analogRead(A0);
    delay(40);  // the sensor only updates every ~38 ms
  }
  // sort the readings, smallest first
  for (int i = 0; i < n; i++)
    for (int j = i + 1; j < n; j++)
      if (r[j] < r[i]) { int t = r[i]; r[i] = r[j]; r[j] = t; }
  return r[n / 2];
}

// Scan row by row. Every row goes left to right so all rows line up.
void scan(int p0, int p1, int ps, int t0, int t1, int ts) {
  Serial.println("# BEGIN");
  Serial.println("pan,tilt,raw");
  for (int t = t0; t <= t1; t += ts) {
    for (int p = p0; p <= p1; p += ps) {
      if (Serial.read() == 'X') {
        Serial.println("# ABORTED");
        moveTo(PAN_HOME, TILT_HOME);
        return;
      }
      moveTo(p, t);
      Serial.print(p); Serial.print(',');
      Serial.print(t); Serial.print(',');
      Serial.println(readSensor(SAMPLES));
    }
  }
  Serial.println("# END");
  moveTo(PAN_HOME, TILT_HOME);
}

void setup() {
  Serial.begin(115200);
  panServo.attach(9);
  tiltServo.attach(10);
  moveTo(PAN_HOME, TILT_HOME);
  delay(BIG_MOVE_MS);
  Serial.println("READY");
}

void loop() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  char cmd = line.charAt(0);
  const char *args = line.c_str() + 1;
  int a, b, c, d, e, f;

  if (cmd == 'P') {
    Serial.println("READY");
  } else if (cmd == 'G' && sscanf(args, "%d %d", &a, &b) == 2) {
    moveTo(a, b);
    Serial.print("OK "); Serial.print(curPan); Serial.print(' '); Serial.println(curTilt);
  } else if (cmd == 'R' && sscanf(args, "%d", &a) == 1) {
    Serial.print("RAW "); Serial.println(readSensor(a));
  } else if (cmd == 'S' && sscanf(args, "%d %d %d %d %d %d", &a, &b, &c, &d, &e, &f) == 6) {
    scan(a, b, c, d, e, f);
  }
}
