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


void setup()
{   
  // Setup Serial
  Serial.begin()


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

}

void openGate(const int pin);
// Assume that applying voltage opens relay (might need to change later)
{
  digitalWrite(pin, HIGH);
  delay()
}

void closeGate(const int pin);
// Assume that low state closes relay (might need to change later)
{
  digitalWrite(pin, LOW);
}
