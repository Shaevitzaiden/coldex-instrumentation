/*
  Pneumatic relay controller -- protocol v2
  =========================================

  Target: Arduino Due driving three 8-channel, active-low relay modules
  (writing LOW energizes a relay channel, writing HIGH releases it).

  Every host message is framed as <...>. Every reply is one line ending in \n.
  Lines starting with '#' are human-readable notes; the desktop app ignores them.

    Host sends        Reply                       Meaning
    ----------        -----                       -------
    <n,s>             1                           relay n (0..23) set to s (0 off, 1 on)
                      0,<code>                    rejected, see ERROR CODES below
    <?>               S,<states>,<modes>          24-character status strings (see below)
    <I>               I,coldex_relay_controller,<protocol>,<channels>
    <X>               1                           ALL relays off immediately (no lockout)

  Status strings (one character per relay, relay 0 first):
    <states> : '1' energized, '0' released, 'E' output pin does not read back
               the level it was driven to (wiring fault / damaged pin)
    <modes>  : 'A' automatic control allowed, 'M' switch panel is in MANUAL

  ERROR CODES (reply "0,<code>")
    1 malformed frame         4 switched again within RELAY_SWITCH_DELAY_MS
    2 relay index out of range 5 output pin readback mismatch after switching
    3 state is not 0 or 1     6 switch panel has this channel in MANUAL
                              7 unknown command letter

  Notes
  - The firmware cannot see real valve position. "Energized" means the Due drove
    the relay input; it does not prove the relay clicked or the valve moved.
  - Switch panel support is off until SWITCH_PANEL_INSTALLED is set to true and
    AUTO_SENSE_PINS is filled in. See firmware/relay_controls/README.md.
  - The communication-loss fail-safe is off until COMMS_TIMEOUT_MS is non-zero.
*/

// ---------------------------------------------------------------------------
// Settings you may need to change
// ---------------------------------------------------------------------------
const unsigned long SERIAL_BAUD = 9600;
const unsigned long RELAY_SWITCH_DELAY_MS = 100;   // minimum time between switches of one relay

// Communication-loss fail-safe. 0 disables it. When non-zero, all relays are
// released if no valid frame arrives for this long. The desktop app polls
// status every second, so 5000 ms is a sensible value once enabled.
const unsigned long COMMS_TIMEOUT_MS = 0;

// Switch panel. When installed, each relay channel has one sense input wired
// to the switch's spare pole. The input is read with INPUT_PULLUP:
//   pole connects the pin to Due GND  -> AUTO (pin reads LOW)
//   pole open                         -> MANUAL (pin reads HIGH)
// Use -1 for a channel that has no switch (always AUTO).
// NEVER connect a sense pin to 5 V or 24 V; the Due is a 3.3 V part.
const bool SWITCH_PANEL_INSTALLED = false;
const int AUTO_SENSE_PINS[24] = {
  -1, -1, -1, -1, -1, -1, -1, -1,
  -1, -1, -1, -1, -1, -1, -1, -1,
  -1, -1, -1, -1, -1, -1, -1, -1
};

// ---------------------------------------------------------------------------
// Fixed hardware description
// ---------------------------------------------------------------------------
const char FIRMWARE_ID[] = "coldex_relay_controller";
const int PROTOCOL_VERSION = 2;

const byte NUM_RELAY_MODULES = 3;
const byte RELAYS_PER_MODULE = 8;
const byte NUM_RELAY_CHANNELS = NUM_RELAY_MODULES * RELAYS_PER_MODULE;

const int RELAY_PINS[NUM_RELAY_CHANNELS] = {
  22, 23, 24, 25, 26, 27, 28, 29,   // module 1 -> relays 0..7
  32, 33, 34, 35, 36, 37, 38, 39,   // module 2 -> relays 8..15
  42, 43, 44, 45, 46, 47, 48, 49    // module 3 -> relays 16..23
};

enum ErrorCode {
  ERR_MALFORMED = 1,
  ERR_BAD_INDEX = 2,
  ERR_BAD_STATE = 3,
  ERR_SWITCH_DELAY = 4,
  ERR_READBACK = 5,
  ERR_MANUAL_MODE = 6,
  ERR_UNKNOWN_COMMAND = 7
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const byte MAX_MESSAGE_CHARS = 32;
char receivedChars[MAX_MESSAGE_CHARS];
bool newData = false;

bool relayActive[NUM_RELAY_CHANNELS];
unsigned long lastSwitchMs[NUM_RELAY_CHANNELS];
unsigned long lastValidFrameMs = 0;
bool commsTimedOut = false;

// ---------------------------------------------------------------------------
// Setup / loop
// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(SERIAL_BAUD);

  for (byte i = 0; i < NUM_RELAY_CHANNELS; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
    driveRelay(i, false);
    // Permit a command immediately after boot.
    lastSwitchMs[i] = millis() - RELAY_SWITCH_DELAY_MS;

    if (SWITCH_PANEL_INSTALLED && AUTO_SENSE_PINS[i] >= 0) {
      pinMode(AUTO_SENSE_PINS[i], INPUT_PULLUP);
    }
  }
  lastValidFrameMs = millis();
  Serial.println("# coldex_relay_controller booted, all relays released");
}

void loop() {
  receiveFramedMessage();
  if (newData) {
    handleMessage();
    newData = false;
  }
  checkCommsTimeout();
}

// ---------------------------------------------------------------------------
// Relay helpers
// ---------------------------------------------------------------------------
void driveRelay(byte channel, bool active) {
  digitalWrite(RELAY_PINS[channel], active ? LOW : HIGH);  // active-low boards
  relayActive[channel] = active;
}

bool outputReadsBack(byte channel) {
  // On the Due, digitalRead() of an OUTPUT pin returns the level actually on
  // the pin. A mismatch means the pin is shorted, overloaded or damaged.
  const int expected = relayActive[channel] ? LOW : HIGH;
  return digitalRead(RELAY_PINS[channel]) == expected;
}

bool autoAllowed(byte channel) {
  if (!SWITCH_PANEL_INSTALLED || AUTO_SENSE_PINS[channel] < 0) {
    return true;
  }
  return digitalRead(AUTO_SENSE_PINS[channel]) == LOW;
}

void releaseAllRelays() {
  for (byte i = 0; i < NUM_RELAY_CHANNELS; i++) {
    driveRelay(i, false);
    lastSwitchMs[i] = millis();
  }
}

// Returns 0 on success, otherwise an ErrorCode.
int setRelay(int channel, int requestedState) {
  if (channel < 0 || channel >= NUM_RELAY_CHANNELS) {
    return ERR_BAD_INDEX;
  }
  if (requestedState != 0 && requestedState != 1) {
    return ERR_BAD_STATE;
  }
  if (!autoAllowed(channel)) {
    return ERR_MANUAL_MODE;
  }

  const bool active = (requestedState == 1);
  if (relayActive[channel] == active) {
    // Already in the requested state: report success without re-switching so
    // a repeated command is never rejected by the lockout.
    return outputReadsBack(channel) ? 0 : ERR_READBACK;
  }

  const unsigned long now = millis();
  if ((now - lastSwitchMs[channel]) < RELAY_SWITCH_DELAY_MS) {
    return ERR_SWITCH_DELAY;
  }

  driveRelay(channel, active);
  lastSwitchMs[channel] = now;
  delayMicroseconds(50);  // let the pin settle before reading it back
  return outputReadsBack(channel) ? 0 : ERR_READBACK;
}

// ---------------------------------------------------------------------------
// Communication-loss fail-safe
// ---------------------------------------------------------------------------
void checkCommsTimeout() {
  if (COMMS_TIMEOUT_MS == 0 || commsTimedOut) {
    return;
  }
  if ((millis() - lastValidFrameMs) > COMMS_TIMEOUT_MS) {
    releaseAllRelays();
    commsTimedOut = true;
    Serial.println("# communication timeout: all relays released");
  }
}

// ---------------------------------------------------------------------------
// Serial protocol
// ---------------------------------------------------------------------------
void receiveFramedMessage() {
  static bool receiving = false;
  static byte index = 0;
  const char START_MARKER = '<';
  const char END_MARKER = '>';

  while (Serial.available() > 0 && !newData) {
    const char c = Serial.read();

    if (!receiving) {
      if (c == START_MARKER) {
        receiving = true;
        index = 0;
      }
      continue;
    }

    if (c == START_MARKER) {
      // A new frame started before the old one ended: drop the partial frame.
      index = 0;
      continue;
    }
    if (c == END_MARKER) {
      receivedChars[index] = '\0';
      receiving = false;
      index = 0;
      newData = true;
      return;
    }
    if (index < MAX_MESSAGE_CHARS - 1) {
      receivedChars[index++] = c;
    }
    // Extra characters are discarded until END_MARKER so an oversized frame
    // cannot write past receivedChars.
  }
}

void replyError(int code) {
  Serial.print("0,");
  Serial.println(code);
}

void replyStatus() {
  Serial.print("S,");
  for (byte i = 0; i < NUM_RELAY_CHANNELS; i++) {
    if (!outputReadsBack(i)) {
      Serial.print('E');
    } else {
      Serial.print(relayActive[i] ? '1' : '0');
    }
  }
  Serial.print(',');
  for (byte i = 0; i < NUM_RELAY_CHANNELS; i++) {
    Serial.print(autoAllowed(i) ? 'A' : 'M');
  }
  Serial.println();
}

void replyIdentity() {
  Serial.print("I,");
  Serial.print(FIRMWARE_ID);
  Serial.print(',');
  Serial.print(PROTOCOL_VERSION);
  Serial.print(',');
  Serial.println(NUM_RELAY_CHANNELS);
}

// Parse a strict non-negative decimal integer. Returns -1 if text is empty or
// contains anything other than digits (atoi() would silently accept "3x").
int parseIndex(const char *text) {
  if (text == NULL || *text == '\0') {
    return -1;
  }
  long value = 0;
  for (const char *p = text; *p != '\0'; p++) {
    if (*p < '0' || *p > '9') {
      return -1;
    }
    value = value * 10 + (*p - '0');
    if (value > 1000) {
      return 1000;  // clearly out of range; reported as ERR_BAD_INDEX
    }
  }
  return (int)value;
}

void handleMessage() {
  // Any well-formed frame counts as the host being alive.
  lastValidFrameMs = millis();
  if (commsTimedOut) {
    commsTimedOut = false;
    Serial.println("# communication restored");
  }

  // Single-letter commands.
  if (receivedChars[0] != '\0' && receivedChars[1] == '\0') {
    switch (receivedChars[0]) {
      case '?': replyStatus(); return;
      case 'I': replyIdentity(); return;
      case 'X': releaseAllRelays(); Serial.println(1); return;
      default:
        if (receivedChars[0] < '0' || receivedChars[0] > '9') {
          replyError(ERR_UNKNOWN_COMMAND);
          return;
        }
    }
  }

  // <relay_index,state>
  char *indexText = strtok(receivedChars, ",");
  char *stateText = strtok(NULL, ",");
  if (indexText == NULL || stateText == NULL || strtok(NULL, ",") != NULL) {
    replyError(ERR_MALFORMED);
    return;
  }
  const int channel = parseIndex(indexText);
  const int requestedState = parseIndex(stateText);
  if (channel < 0 || requestedState < 0) {
    replyError(ERR_MALFORMED);
    return;
  }

  const int result = setRelay(channel, requestedState);
  if (result == 0) {
    Serial.println(1);
  } else {
    replyError(result);
  }
}
