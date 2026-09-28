/*
  MP2 HARDWARE TEST - run this BEFORE the scanner sketch
  -------------------------------------------------------
  Same wiring as the scanner: pan servo D9, tilt servo D10, Sharp sensor Vo on A0.

  How to use:
    1. Upload this sketch.
    2. Open Tools > Serial Monitor, set 115200 baud, line ending "Newline".
    3. Type a command and press Enter.  Type h for the menu.

  Commands
    1        sensor LIVE readout (raw, volts, approx cm). Press Enter again to stop.
             Also works in Tools > Serial Plotter to see noise as a graph.
    2        sensor NOISE check: 50 readings, reports min/max/spread
    3        PAN sweep test   (slow sweep across SWEEP range and back)
    4        TILT sweep test
    5        POWER stress test: both servos move fast while reading the sensor
    c        centre both servos (90, 90)
    a / d    pan  -1 / +1 deg     (A / D = 5 deg; "aaaa" = 4 steps)
    s / w    tilt -1 / +1 deg     (S / W = 5 deg)
    g P T    go to pan P, tilt T  e.g.  g 80 95
    r        one reading at the current position
    h        help

  "*** BOOT ***" appearing again at any point means the Arduino RESET,
  almost always because the servos pulled too much current (see schematic note 5).
*/

#include <Servo.h>

const uint8_t PAN_PIN = 9, TILT_PIN = 10, SENSOR_PIN = A0;

// Sweep limits for tests 3-5. Start narrow; widen once you know the mount has clearance.
const int PAN_SWEEP_MIN = 45,  PAN_SWEEP_MAX = 135;
const int TILT_SWEEP_MIN = 60, TILT_SWEEP_MAX = 120;
// Hard limits for manual jogging
const int PAN_MIN = 0, PAN_MAX = 180, TILT_MIN = 30, TILT_MAX = 150;

Servo panServo, tiltServo;
int pan = 90, tilt = 90;

// ---------------------------------------------------------------- helpers
// Typical GP2Y0A02 curve. ONLY a rough sanity check - your real calibration replaces it.
float approxCm(int raw) {
  if (raw < 20) return -1;                        // basically no return
  return 19080.0 * pow((float)raw, -1.10);
}

void setServos(int p, int t) {
  pan = constrain(p, PAN_MIN, PAN_MAX);
  tilt = constrain(t, TILT_MIN, TILT_MAX);
  panServo.write(pan);
  tiltServo.write(tilt);
}

void printPos() {
  Serial.print(F("pan=")); Serial.print(pan);
  Serial.print(F("  tilt=")); Serial.println(tilt);
}

void printReading(int raw) {
  Serial.print(F("raw:")); Serial.print(raw);
  Serial.print(F(",volts:")); Serial.print(raw * 5.0 / 1023.0, 2);
  Serial.print(F(",approx_cm:")); Serial.println(approxCm(raw), 1);
}

bool keyPressed() {                 // true if the user sent anything (used to stop tests)
  if (!Serial.available()) return false;
  while (Serial.available()) Serial.read();
  return true;
}

void flushInput() { delay(20); while (Serial.available()) Serial.read(); }

// ---------------------------------------------------------------- tests
void testSensorLive() {
  Serial.println(F("\n[1] LIVE sensor. Move your hand/cardboard in front of it. Press Enter to stop."));
  flushInput();
  while (!keyPressed()) {
    printReading(analogRead(SENSOR_PIN));
    delay(100);
  }
  Serial.println(F("stopped."));
}

void testSensorNoise() {
  Serial.println(F("\n[2] NOISE check. Hold a flat target still ~50 cm away..."));
  delay(1500);
  const int N = 50;
  long sum = 0; int mn = 1023, mx = 0;
  for (int i = 0; i < N; i++) {
    int r = analogRead(SENSOR_PIN);
    sum += r; mn = min(mn, r); mx = max(mx, r);
    delay(40);                      // sensor updates every ~38 ms
  }
  int mean = sum / N, spread = mx - mn;
  Serial.print(F("mean raw ")); Serial.print(mean);
  Serial.print(F(" (~")); Serial.print(approxCm(mean), 1); Serial.print(F(" cm)"));
  Serial.print(F("   min ")); Serial.print(mn);
  Serial.print(F("   max ")); Serial.print(mx);
  Serial.print(F("   spread ")); Serial.println(spread);

  if (mean < 20)       Serial.println(F("FAIL: reading ~0. Check Vo -> A0 and that Vcc/GND are connected."));
  else if (mean > 900) Serial.println(F("FAIL: reading near max. Vo may be shorted to 5V, or wires swapped."));
  else if (spread > 25) Serial.println(F("NOISY: add/check the 10 uF capacitor at the sensor; check loose wires."));
  else                 Serial.println(F("PASS: sensor looks healthy."));
}

void sweep(bool isPan) {
  int lo = isPan ? PAN_SWEEP_MIN : TILT_SWEEP_MIN;
  int hi = isPan ? PAN_SWEEP_MAX : TILT_SWEEP_MAX;
  Serial.print(isPan ? F("\n[3] PAN") : F("\n[4] TILT"));
  Serial.print(F(" sweep ")); Serial.print(lo); Serial.print(F("..")); Serial.print(hi);
  Serial.println(F(" and back. Press Enter to stop early."));
  Serial.println(F("Watch for: smooth motion, no buzzing/stalling, nothing hitting the frame."));
  flushInput();
  setServos(isPan ? lo : pan, isPan ? tilt : lo);
  delay(600);
  for (int pass = 0; pass < 2; pass++) {
    for (int a = lo; a <= hi; a++) {
      int ang = pass == 0 ? a : hi - (a - lo);
      if (isPan) setServos(ang, tilt); else setServos(pan, ang);
      if (ang % 15 == 0) printPos();
      delay(25);
      if (keyPressed()) { Serial.println(F("stopped.")); return; }
    }
  }
  setServos(90, 90);
  Serial.println(F("done - servos re-centred."));
}

void testPower() {
  Serial.println(F("\n[5] POWER stress: both servos swing fast 5 times while reading the sensor."));
  Serial.println(F("Keep a target ~50 cm in front. If you see *** BOOT *** afterwards, power is inadequate."));
  flushInput();
  setServos(90, 90); delay(500);
  int baseline = analogRead(SENSOR_PIN);
  int worst = 0;
  for (int i = 0; i < 5; i++) {
    setServos(PAN_SWEEP_MIN + 15, TILT_SWEEP_MIN + 10); delay(350);
    worst = max(worst, abs(analogRead(SENSOR_PIN) - baseline) );
    setServos(PAN_SWEEP_MAX - 15, TILT_SWEEP_MAX - 10); delay(350);
    worst = max(worst, abs(analogRead(SENSOR_PIN) - baseline) );
    Serial.print(F("  cycle ")); Serial.println(i + 1);
  }
  setServos(90, 90); delay(500);
  int after = analogRead(SENSOR_PIN);
  Serial.print(F("baseline raw ")); Serial.print(baseline);
  Serial.print(F(", after ")); Serial.print(after);
  Serial.print(F(", largest change while moving ")); Serial.println(worst);
  Serial.println(F("Survived without a reset: PASS."));
  if (abs(after - baseline) > 25)
    Serial.println(F("Note: reading changed after moving. Did the target/scene change? If not, check power/ground wiring."));
  Serial.println(F("(Large changes WHILE moving are normal - the sensor is pointing at different things.)"));
}

void help() {
  Serial.println(F("\n--- MP2 hardware test ---"));
  Serial.println(F("1 sensor live | 2 noise check | 3 pan sweep | 4 tilt sweep | 5 power stress"));
  Serial.println(F("c centre | a/d pan -/+1 (A/D 5) | s/w tilt -/+1 (S/W 5) | g P T goto | r read | h help"));
  printPos();
}

// ---------------------------------------------------------------- main
void setup() {
  Serial.begin(115200);
  panServo.attach(PAN_PIN);
  tiltServo.attach(TILT_PIN);
  setServos(90, 90);
  delay(300);
  Serial.println(F("\n*** BOOT ***  (if you see this again later, the Arduino reset)"));
  help();
}

void loop() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) return;
  char c = line.charAt(0);

  // jog keys: every character in the line counts, so "dddd" = +4 deg
  if (strchr("aAdDsSwW", c)) {
    for (unsigned i = 0; i < line.length(); i++) {
      switch (line.charAt(i)) {
        case 'a': pan -= 1; break;   case 'A': pan -= 5; break;
        case 'd': pan += 1; break;   case 'D': pan += 5; break;
        case 's': tilt -= 1; break;  case 'S': tilt -= 5; break;
        case 'w': tilt += 1; break;  case 'W': tilt += 5; break;
      }
    }
    setServos(pan, tilt);
    printPos();
    return;
  }

  int p, t;
  switch (c) {
    case '1': testSensorLive(); break;
    case '2': testSensorNoise(); break;
    case '3': sweep(true); break;
    case '4': sweep(false); break;
    case '5': testPower(); break;
    case 'c': case 'C': setServos(90, 90); printPos(); break;
    case 'r': case 'R': printPos(); printReading(analogRead(SENSOR_PIN)); break;
    case 'g': case 'G':
      if (sscanf(line.c_str() + 1, "%d %d", &p, &t) == 2) { setServos(p, t); printPos(); }
      else Serial.println(F("usage: g 80 95"));
      break;
    case 'h': case 'H': case '?': help(); break;
    default: Serial.println(F("unknown command - type h"));
  }
}
