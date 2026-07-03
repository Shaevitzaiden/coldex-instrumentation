#include <Wire.h>
#include <PWFusion_Mcp960x.h>

Mcp960x thermo1;

#define ERR_THERMOCOUPLE_STARTUP        0x0F
#define ERR_THERMOCOUPLE_OPEN_CIRCUIT   0x10
#define ERR_THERMOCOUPLE_SHORT_CIRCUIT  0x11
#define ERR_THERMOCOUPLE_PENDING        0x12


float temp = 0;


void setup() {
  // Initialize I2C and serial port
  Wire.begin();
  Wire.setClock(100000);
  Serial.begin(250000);

  // Initialize MCP9601 with address 1
  thermo1.begin(1);
  if (thermo1.isConnected()) {
     thermo1.setThermocoupleType(TYPE_K);
     thermo1.setResolution(RES_18BIT, RES_0p0625);
  }
  else {
    Serial.println(ERR_THERMOCOUPLE_STARTUP);
  }
}

void loop() {  
  // Serial.print(F("Thermocouple Temperature: "));
  
  switch (thermo1.getStatus()) {
    case OPEN_CIRCUIT:
      Serial.println(ERR_THERMOCOUPLE_OPEN_CIRCUIT);
      break;

    case SHORT_CIRCUIT:
      Serial.println(ERR_THERMOCOUPLE_SHORT_CIRCUIT);
      break;

    case READY:
      temp = thermo1.getThermocoupleTemp();
      Serial.println(temp);
      break;

    default:
      Serial.println(ERR_THERMOCOUPLE_PENDING);
      break;
  }

  // Serial.print(F("Ambient Temperature: "));
  // Serial.println(thermo1.getColdJunctionTemp());
  // Serial.println();

  delay(500);
}