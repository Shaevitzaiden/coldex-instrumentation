# MCP9601 thermocouple reader example

Target: Arduino-compatible controller connected to an MCP9601 through I2C, using the `PWFusion_Mcp960x` library.

## Current behavior

- I2C clock: 100 kHz
- Thermocouple type: K
- Serial baud: 9600
- Sampling interval: 500 ms
- Temperature output: floating-point °C, one line per sample

Status/error lines:

| Decimal | Hex | Meaning |
|---:|---:|---|
| 15 | `0x0F` | MCP9601 startup/connection failure |
| 16 | `0x10` | open thermocouple circuit |
| 17 | `0x11` | short-circuit status |
| 18 | `0x12` | conversion pending/other non-ready state |

The startup device ID is printed with a `#` prefix so a future host parser can distinguish diagnostic text from samples.

## Integration status

This firmware is **not yet connected to the main DeviceManager/DataHub path**. If it is brought back into service, add a communicator that parses the numeric/status stream and publishes a normalized temperature sensor frame.
