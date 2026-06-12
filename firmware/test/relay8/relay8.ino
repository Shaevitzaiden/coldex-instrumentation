// Serial Comm Parameters
const int serial_clock = 250000; // baud rate


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
