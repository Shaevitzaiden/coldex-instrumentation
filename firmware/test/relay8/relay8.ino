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
// const float relay_switch_delay = 100.0; // ms
// float relay_switching_timers[8] = {}; // ms

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
delay(1);
}


void openGate(const int relay)
// Assume that applying voltage opens relay (might need to change later)
{
  int pin = relayToPin(relay);
  digitalWrite(pin, HIGH);
}

void closeGate(const int relay)
// Assume that low state closes relay (might need to change later)
{
  int pin = relayToPin(relay);
  digitalWrite(pin, LOW);
}

int relayToPin(int relay)
// Convenience function to use relay names more broadly instead of directly associating with physical pin numbers
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
