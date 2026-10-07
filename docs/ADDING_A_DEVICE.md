# Adding a new instrument

You need three things: a **driver** (a small Python file that talks to the
instrument), an entry in **`config/devices.yaml`**, and the instrument's
channels in **`config/sensors.yaml`**. You do not edit `run_app.py` or any of
the GUI code.

## 1. Check whether a driver already exists

```text
python run_app.py --list-drivers
```

If your instrument is listed, skip to step 3.

## 2. Write a driver

Copy `src/pneumatic_valve_panel/drivers/_template.py` to a new file in the
same folder, for example `drivers/my_gauge.py`. Files in that folder are
loaded automatically; files whose name starts with `_` are skipped.

The template has two examples. Keep the one that fits and delete the other.

**A. The instrument prints one reading per line** (typical Arduino sensor).
Write one method, `parse_line`, that turns a line of text into numbers:

```python
from . import register_driver
from .line_sensor import LineSerialSensor


@register_driver("my_gauge")
class MyGauge(LineSerialSensor):
    """My gauge: prints the pressure in Torr on each line."""

    def parse_line(self, line):
        return {"pressure": float(line)}
```

`drivers/mcp9601_thermocouple.py` is a complete real example.

**B. The instrument must be asked for each reading** (typical lab
controller). Write `connect`, `disconnect` and `read_available_packets`, as
in the template's `ExamplePolledGauge`. The app calls
`read_available_packets` many times a second, so return `[]` until it is
time for the next reading.

Rules the app relies on:

- Raise an exception from `connect` if the instrument is not there. The app
  shows the message and retries.
- Raise `ConnectionError` (or let a serial error escape) when the link is
  lost; the app reconnects. Raise `TimeoutError` for a single missed reply.
- Never call GUI code from a driver. Each driver runs in its own thread.

## 3. Add it to `config/devices.yaml`

```yaml
  my_gauge:
    enabled: true
    driver: my_gauge
    description: Chamber pressure gauge
    connection:
      port: COM7        # Windows Device Manager -> Ports (COM & LPT)
      baudrate: 9600
```

Optional keys: `options:` (passed to the driver class), `demo_driver:` (a
simulated stand-in for `--demo`), `reconnect_interval_s:` (default 5).

## 4. Add its channels to `config/sensors.yaml`

```yaml
  my_gauge.pressure:
    label: Chamber Pressure
    source_device: my_gauge     # the device id from devices.yaml
    source_channel: pressure    # the name your driver returns
    unit: Torr
    expected_sampling_hz: 1
    enabled: true
    default_log: true
    metadata:
      quantity: pressure
```

## 5. Try it

```text
python run_app.py
```

The **Device Connectivity** tile shows whether it connected and, if not, why.
The **Log** tile shows warnings from your driver. To check the parsing
without hardware, add a test in `tests/` modelled on `tests/test_drivers.py`
and run `pytest`.
