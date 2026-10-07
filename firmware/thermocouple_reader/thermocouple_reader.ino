/*
  MCP9601 K-type thermocouple reader
  ==================================

  Serial output is intentionally simple so the desktop application can parse
  one value/status per line at 9600 baud:

    floating-point number : thermocouple temperature in degrees C
    15                    : startup / MCP9601 connection failure
    16                    : open thermocouple circuit
    17                    : short-circuit status
    18                    : conversion pending / other non-ready status

  The MCP9601 is configured for a K-type thermocouple and 18-bit hot-junction
  conversion. The diagnostic firmware previously halted forever after printing
  the device ID; that halt has been removed so normal sampling now runs.
*/

#include <Wire.h>
#include <PWFusion_Mcp960x.h>

Mcp960x thermo1;

#define ERR_THERMOCOUPLE_STARTUP        0x0F
#define ERR_THERMOCOUPLE_OPEN_CIRCUIT   0x10
#define ERR_THERMOCOUPLE_SHORT_CIRCUIT  0x11
#define ERR_THERMOCOUPLE_PENDING        0x12

bool thermocoupleConnected = false;

void setup() {
  Wire.begin();
  Wire.setClock(100000);
  Serial.begin(9600);

  // The library's begin() argument is the address selector used by the
  // existing board/wiring. Re-check this value if A0/A1 address straps change.
  thermo1.begin(1);
  thermocoupleConnected = thermo1.isConnected();

  if (!thermocoupleConnected) {
    Serial.println(ERR_THERMOCOUPLE_STARTUP);
    return;
  }

  thermo1.setThermocoupleType(TYPE_K);
  thermo1.setResolution(RES_18BIT, RES_0p0625);

  // One startup diagnostic line is useful on a terminal but is prefixed so it
  // cannot be mistaken for a temperature sample by a future parser.
  const uint16_t id = thermo1.readWord(REG_DEV_ID);
  Serial.print("# MCP9601 ID/revision: 0x");
  Serial.println(id, HEX);
}

void loop() {
  if (!thermocoupleConnected) {
    Serial.println(ERR_THERMOCOUPLE_STARTUP);
    delay(1000);
    return;
  }

  switch (thermo1.getStatus()) {
    case OPEN_CIRCUIT:
      Serial.println(ERR_THERMOCOUPLE_OPEN_CIRCUIT);
      break;

    case SHORT_CIRCUIT:
      Serial.println(ERR_THERMOCOUPLE_SHORT_CIRCUIT);
      break;

    case READY:
      Serial.println(thermo1.getThermocoupleTemp());
      break;

    default:
      Serial.println(ERR_THERMOCOUPLE_PENDING);
      break;
  }

  delay(500);
}
