"""Feather RP2040 Adalogger native-ADC DAQ, CircuitPython example.

Uses A0-A3 with a 30.1k/10.0k divider and 100 nF capacitor per channel.
Emits the same newline-delimited JSON protocol as the Arduino and ADS1115
examples. CircuitPython AnalogIn.value is reported as a 16-bit-scaled value,
but the underlying RP2040 ADC hardware is 12-bit.
"""

import analogio
import board
import json
import supervisor
import time

ADC_REFERENCE_V = 3.3000
R_TOP_OHM = 30100.0
R_BOTTOM_OHM = 10000.0
DIVIDER_GAIN = (R_TOP_OHM + R_BOTTOM_OHM) / R_BOTTOM_OHM
AVERAGES = 64
CAL_SCALE = [1.0, 1.0, 1.0, 1.0]
CAL_OFFSET_V = [0.0, 0.0, 0.0, 0.0]

channels = [
    analogio.AnalogIn(board.A0),
    analogio.AnalogIn(board.A1),
    analogio.AnalogIn(board.A2),
    analogio.AnalogIn(board.A3),
]

streaming = False
sample_rate_hz = 10.0
next_sample = time.monotonic()
line_buffer = ""


def read_voltage(ch):
    total = 0
    for _ in range(AVERAGES):
        total += channels[ch].value
    avg = total / AVERAGES
    adc_v = avg / 65535.0 * ADC_REFERENCE_V
    input_v = adc_v * DIVIDER_GAIN
    return input_v * CAL_SCALE[ch] + CAL_OFFSET_V[ch]


def sample():
    return {
        "type": "sample",
        "t_us": int(time.monotonic_ns() // 1000),
        "volts": [read_voltage(i) for i in range(4)],
    }


def emit(obj):
    print(json.dumps(obj))


def info():
    emit({
        "type": "info",
        "device": "adalogger_native_adc",
        "adc": "rp2040_12bit",
        "channels": 4,
        "divider_gain": DIVIDER_GAIN,
        "adc_reference_v": ADC_REFERENCE_V,
        "averages": AVERAGES,
    })


def handle(cmd):
    global streaming, sample_rate_hz, next_sample
    cmd = cmd.strip().upper()
    if cmd == "PING":
        emit({"type": "ack", "command": "PING", "value": "PONG"})
    elif cmd == "INFO":
        info()
    elif cmd == "READ":
        emit(sample())
    elif cmd == "START":
        streaming = True
        next_sample = time.monotonic()
        emit({"type": "ack", "command": "START"})
    elif cmd == "STOP":
        streaming = False
        emit({"type": "ack", "command": "STOP"})
    elif cmd.startswith("RATE "):
        try:
            requested = float(cmd.split(maxsplit=1)[1])
            if not 0.2 <= requested <= 50.0:
                raise ValueError
            sample_rate_hz = requested
            emit({"type": "ack", "command": "RATE", "hz": sample_rate_hz})
        except ValueError:
            emit({"type": "error", "message": "RATE must be 0.2..50 Hz"})
    else:
        emit({"type": "error", "message": "unknown command"})


info()
while True:
    if supervisor.runtime.serial_bytes_available:
        c = input().strip()
        if c:
            handle(c)

    if streaming and time.monotonic() >= next_sample:
        emit(sample())
        next_sample += 1.0 / sample_rate_hz
        if time.monotonic() - next_sample > 2.0 / sample_rate_hz:
            next_sample = time.monotonic() + 1.0 / sample_rate_hz

    time.sleep(0.001)
