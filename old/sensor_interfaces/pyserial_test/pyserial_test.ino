// Serial read parameters
const byte numChars = 32; // expected maximum input length: 32 bits
char receivedChars[numChars];   // an array to store the received data
boolean newData = false;  // flag to keep track of if we have new data to process or not

// Define input options - the serial message will come in from Pyserial as an integer, but that's not
// very human-readable
#define pinLow 00
#define pinHigh 01
const char delimiter = ';';
// Create arrays to sort out the pin and command values from the serial input
char cmd[3];
char mypin[3];

// Make sure the serial is set up
void setup() {
  Serial.begin(19200);
  while (!Serial); // Wait out until serial starts up
  delay(100);
  clearInputBuffer();
  Serial.println("Ready to recieve serial commands");
}

// Then loop forever reading serial input
void loop() {
  recvWithStartEndMarker();
  parseCommands();
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
    // Create indices for our command and pin arrays
    int cIdx = 0;
    int pIdx = 0;
    // Create a flag to see if we've hit the delimieter
    boolean hitDel = false;
    // Loop through the received input array, splitting it into the command (before delimiter) and
    // pin (after delimiter) segements
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

    // Sanity check for debugging - did we get the expected values?
    // Serial.print("command ");
    // Serial.println(cmd);
    // Serial.print("pin ");
    // Serial.println(mypin);
    
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

void setPinLow(int pin){
  pinMode(pin, OUTPUT);
  digitalWrite(pin, LOW);
  Serial.print("Pin ");
  Serial.print(pin);
  Serial.print(" set ");
  Serial.println(digitalRead(pin));
}

void setPinHigh(int pin){
  pinMode(pin, OUTPUT);
  digitalWrite(pin, HIGH);
  Serial.print("Pin ");
  Serial.print(pin);
  Serial.print(" set ");
  Serial.println(digitalRead(pin));
}

void clearInputBuffer() {
  while (Serial.available() > 0) {
    Serial.read();
  }
}