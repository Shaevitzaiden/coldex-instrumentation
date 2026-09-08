# Arduino firmware
Board: Adafruit Feather RP2040 Adalogger. Install the Adafruit RP2040 board package and **Adafruit ADS1X15** library. Connect the ADS1115 by STEMMA QT/Qwiic or SDA/SCL. Open the native USB serial port at 115200 baud.

Commands: `PING`, `INFO`, `READ`, `START`, `STOP`, `RATE <Hz>`. Output is newline-delimited JSON. `volts[]` are reconstructed **instrument-side** voltages using a 49.9k/10k divider.
