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
const int relay_pins[3][8] = {
  {4,  5,  6,  7,  8,  9,  10, 11}, // Relay module 1
  {12, 13, 14, 15, 16, 17, 18, 19}, // Relay module 2
  {20, 21, 22, 23, 24, 25, 26, 27}  // Relay module 3
  };

// Relay state management
const int num_relays = 3;
const int num_switches = 8;
const int num_relay_switches = num_relays * num_switches;
const float relay_switch_delay = 100.0;              // (ms), minimum switching delay
unsigned long relay_switching_timers[3][8] = {0.0};  // (ms), timers in ms to prevent rapid relay switching
enum { OPEN,
       CLOSED };    // ---------------- change to match solenoid state and corresponding relay default (open or closed)
int gate_state[3][8];  // This assumes all open (which means nothing physically yet)


void setup() 
{
  // Setup Serial
  Serial.begin(serial_clock);
  clearInputBuffer();

  // Cycle through all pins connected to relays and set them to OUTPUT pins
  for (int relay_module = 0; relay_module < 3; relay_module++) {
    for (int relay_channel = 0; relay_channel < 8; relay_channel++) {
      pinMode(relay_pins[relay_module][relay_channel], OUTPUT);
    }
  }
}

void loop() 
{
  recvWithStartEndMarker();
  
  if (newData) {
  // Serial.println("New data: " + String(newData));
    bool action_completion = parseCommands();
    if (action_completion) {
      Serial.println(SUCCESS);
    } else {
      Serial.println(FAILURE);
    }
  }
}


bool changeRelaySwitchState(const int relay, const int relay_switch, int state) {
    // If cannot switch return
    if (!canSwitch(relay, relay_switch)) {
      return false;
    }
    int pin = relay_pins[relay][relay_switch];
    if (state == 0) { digitalWrite(pin, HIGH); }      // Close the gate (Depends on default setting)
    else if (state == 1) { digitalWrite(pin, LOW); }  // Open the gate
    else { return false; }                            // Invalid state switching request
    relay_switching_timers[relay][relay_switch] = millis();  // Reset delay timer for switch
    return true;
}

bool canSwitch(const int relay, const int relay_switch)
// Check if switch is still on timer delay
{
  float switch_delta = millis() - relay_switching_timers[relay][relay_switch];
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
    if (strtokIndx == NULL) {
    newData = false;
    return false;
    }
    int msb = atoi(strtokIndx);

    strtokIndx = strtok(NULL, ",");  // Get lb, used to decide action on item (ex: open or close valve)
    if (strtokIndx == NULL) {
    newData = false;
    return false;
    }
    int lsb = atoi(strtokIndx);

    // -------- Choose action to take from msg --------
    bool action_success = false;
    // int cmd_return_code[2];
    
    // Acting on a relay switch
    if (msb < num_relay_switches) {
      // Get relay number and switch number from msb
      int relay = (int)floor( (float)msb / ((float)num_switches) );
      int relay_switch = msb % num_switches;
      action_success = changeRelaySwitchState(relay, relay_switch, lsb);
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

