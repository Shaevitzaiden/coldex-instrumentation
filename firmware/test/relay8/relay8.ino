// State machine states (may not be useful but here for now)
enum{
  INIT,
  IDLE,
  ACTIVE,
  ERROR
};
int state = INIT; // Start in init state

// Serial Comm Parameters
const int serial_clock = 250000;  // baud rate
const byte numChars = 32;         // Max serial message length
char receivedChars[numChars];     // Array to store serial msgs
bool newData = false;             // flag to indicate the prescence of a new message



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
enum{RELAY1, RELAY2, RELAY3, RELAY4, RELAY5, RELAY6, RELAY7, RELAY8};
const float relay_switch_delay = 100.0; // (ms), minimum switching delay
unsigned long relay_switching_timers[8] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0}; // (ms), timers in ms to prevent rapid relay switching
enum{OPEN, CLOSED}; // ---------------- change to match solenoid state and corresponding relay default (open or closed)
int gate_state[8]; // This assumes all open (which means nothing physically yet)




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

}

 void loop()
{ 
  // State machine switch/case block
}


bool openGate(const int relay)
// Assume that applying voltage opens relay (might need to change later)
{
  if (canSwitch(relay)){
    int pin = relayToPin(relay);
    digitalWrite(pin, HIGH);
    relay_switching_timers[relay] = millis(); // Reset delay timer for switch
    return true;
  }
  else {
    return false;
  }
}

bool closeGate(const int relay)
// Assume that low state closes relay (might need to change later)
{
  if (canSwitch(relay)){
    int pin = relayToPin(relay);
    digitalWrite(pin, LOW);
    relay_switching_timers[relay] = millis(); // Reset delay timer for switch
    return true;
  }
  else {
    return false;
  }
}

bool canSwitch(const int relay)
// Check if switch is still on timer delay 
{
  float switch_delta =  millis() - relay_switching_timers[relay];
  if (switch_delta > relay_switch_delay) {
    return true; // Switch is off delay
  }
  else {
    return false; // Still on delay
  }
}

int relayToPin(int relay)
// Mapping function to go from relay # to relay pin number
{
  switch (relay){
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

// Function to accept and retain serial input
void recvWithStartEndMarker() {
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

// Function to process serial input
void parseCommands() {
  // If we have new data, process it
  if (newData == true) {
    // Reset the new data flag
    newData = false;

    // Create a flag to see if we've hit the delimiter
    boolean hitDel = false;
    
    // Loop through the received input array, splitting it into the command 
    for (int i=0; i<strlen(receivedChars); i++){
      // Grab the next index of our received input array
      char c = receivedChars[i];
      // If we hit the delimieter, change our flag and skip the rest of that loop
      if (c == delimiter){
        hitDel = true;
        continue;
      }
      // Update either the pin or command arrays accordingly
      if (hitDel == true){
        mypin[pIdx] = c;
        pIdx ++;
      }
      else{
        cmd[cIdx] = c;
        cIdx ++;
      }
    }
    // Terminate the arrays properly
    cmd[cIdx] = '\0';
    mypin[pIdx] = '\0';

    // Convert the input to ints
    int cmdResult = atoi(cmd);
    int pinResult = atoi(mypin);
    
    // Manage the serial input accordingly
    if (pinResult <= 69){
      if (cmdResult == pinLow){
        setPinLow(pinResult);
      }
      else if (cmdResult == pinHigh){
        setPinHigh(pinResult);
      }
      else{
        Serial.println("Unknown command received");
      }
    }
    else{
      Serial.println("Invalid pin received");
    }
  }

}