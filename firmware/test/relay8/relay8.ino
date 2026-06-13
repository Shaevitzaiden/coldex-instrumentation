// State machine states (may not be useful but here for now)
enum {
  INIT,
  IDLE,
  ACTIVE,
  ERROR
};
int state = INIT;  // Start in init state

// Serial Comms
const int serial_clock = 250000;  // baud rate
const byte numChars = 32;         // Max serial message length
char receivedChars[numChars];     // Array to store serial msgs
bool newData = false;             // flag to indicate the prescence of a new message

// Command return messages
#define FAILURE             0x00
#define SUCCESS             0x01
#define RELAY_DELAY_FAILURE 0x02
#define INVALID_ADDR        0x03
#define INVALID_CMD         0x04
#define GATE_STATE_WARNING  0x05

// Define pins for associated relays
const int relay1pin = 4;
const int relay2pin = 5;
const int relay3pin = 6;
const int relay4pin = 7;
const int relay5pin = 8;
const int relay6pin = 9;
const int relay7pin = 10;
const int relay8pin = 11;

// Relay state management
enum { RELAY1,
       RELAY2,
       RELAY3,
       RELAY4,
       RELAY5,
       RELAY6,
       RELAY7,
       RELAY8 };
const int num_relays = 8;
const float relay_switch_delay = 100.0;                                                // (ms), minimum switching delay
unsigned long relay_switching_timers[8] = { 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0 };  // (ms), timers in ms to prevent rapid relay switching
enum { OPEN,
       CLOSED };    // ---------------- change to match solenoid state and corresponding relay default (open or closed)
int gate_state[8];  // This assumes all open (which means nothing physically yet)




void setup() 
{
  // Setup Serial
  Serial.begin(serial_clock);

  // Set relay pins as output pins
  pinMode(relay1pin, OUTPUT);
  pinMode(relay2pin, OUTPUT);
  pinMode(relay3pin, OUTPUT);
  pinMode(relay4pin, OUTPUT);
  pinMode(relay5pin, OUTPUT);
  pinMode(relay6pin, OUTPUT);
  pinMode(relay7pin, OUTPUT);
  pinMode(relay8pin, OUTPUT);

  // Wait for startup message
  pinMode(LED_BUILTIN, OUTPUT);
  while (Serial.available() <= 0) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(500);
    digitalWrite(LED_BUILTIN, LOW);
    delay(500);
  }

}

void loop() 
{
  recvWithStartEndMarker();
  if (newData) {
    
    bool action_completion = parseCommands();
    if (action_completion) {
      Serial.println(SUCCESS);
    } else {
      Serial.println(FAILURE);
    }
  }
}


bool openGate(const int relay)
// Assume that applying voltage opens relay (might need to change later)
{
  if (canSwitch(relay)) {
    int pin = relayToPin(relay);
    digitalWrite(pin, HIGH);
    relay_switching_timers[relay] = millis();  // Reset delay timer for switch
    return true;
  } else {
    return false;
  }
}

bool closeGate(const int relay)
// Assume that low state closes relay (might need to change later)
{
  if (canSwitch(relay)) {
    int pin = relayToPin(relay);
    digitalWrite(pin, LOW);
    relay_switching_timers[relay] = millis();  // Reset delay timer for switch
    return true;
  } else {
    return false;
  }
}

bool canSwitch(const int relay)
// Check if switch is still on timer delay
{
  float switch_delta = millis() - relay_switching_timers[relay];
  if (switch_delta > relay_switch_delay) {
    return true;  // Switch is off delay
  } else {
    return false;  // Still on delay
  }
}

// Function to accept and retain serial input
void recvWithStartEndMarker() 
{
  static boolean recvInProgress = false;
  static byte ndx = 0;
  char startMarker = '<';
  char endMarker = '>';
  char rc;

  // Loop through the serial message until we receive an end character.
  while (Serial.available() > 0 && newData == false) {
    // Read one byte.
    rc = Serial.read();
    // If we're currently reading data:
    if (recvInProgress == true) {
      // If we haven't received an "end" char,
      if (rc != endMarker) {
        // Add the char to our data array and increase the index.
        receivedChars[ndx] = rc;
        ndx++;
        // If we've received more than the expected 32 bits, no we haven't.
        if (ndx >= numChars) {
          ndx = numChars - 1;
        }
      }
      // Otherwise, we've received an "end" char.
      else {
        // Terminate the string
        receivedChars[ndx] = '\0';
        // Reset the flags for the next command
        recvInProgress = false;
        ndx = 0;
        newData = true;
      }
    }
    // Otherwise, check if the character is our "start" char. If so, we should start reading data...
    else if (rc == startMarker) {
      // So set that flag appropriately.
      recvInProgress = true;
    }
  }
}

// Breakdown msg and execute commands
bool parseCommands() 
{
  if (newData) {
    // -------- Break down msg into parts --------
    char* strtokIndx;

    strtokIndx = strtok(receivedChars, ",");  // Get msb, used to pick item to act on (ex: select valve number)
    int msb = atoi(strtokIndx);

    strtokIndx = strtok(NULL, ",");  // Get lb, used to decide action on item (ex: open or close valve)
    int lsb = atoi(strtokIndx);

    // -------- Choose action to take from msg --------
    bool action_success = false;
    // int cmd_return_code[2];
    // Acting on a relay switch
    if (msb < num_relays) {
      if (lsb == 0) {
        action_success = openGate(msb);
      } 
      else if (lsb == 1) {
        action_success = closeGate(lsb);
      } 
      else {
        action_success = false;
      }
    } 
    else {
      action_success = false;
    }
    newData = false;
    return action_success;
  }
}

void clearInputBuffer() 
{
  while (Serial.available() > 0) {
    Serial.read();
  }
}

int relayToPin(int relay)
// Mapping function to go from relay # to relay pin number
{
  switch (relay) {
    case RELAY1:
      return relay1pin;
    case RELAY2:
      return relay2pin;
    case RELAY3:
      return relay3pin;
    case RELAY4:
      return relay4pin;
    case RELAY5:
      return relay5pin;
    case RELAY6:
      return relay6pin;
    case RELAY7:
      return relay7pin;
    case RELAY8:
      return relay8pin;
    default:
      return 0;
  }
}