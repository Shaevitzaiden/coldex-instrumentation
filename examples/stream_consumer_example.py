"""Example non-GUI consumer suitable for a future automation worker."""

import queue

from pneumatic_valve_panel.data import OverflowPolicy, SensorFrame, StreamHub


def consume_pressure_frames(stream_hub: StreamHub, stop_event) -> None:
    """Read the same controller frames used by plots and the recorder."""

    subscription = stream_hub.subscribe(
        "frames/controller",
        queue_size=1000,
        overflow_policy=OverflowPolicy.DROP_OLDEST,
        name="example-automation",
    )
    try:
        while not stop_event.is_set():
            try:
                envelope = subscription.get(timeout=0.1)
            except queue.Empty:
                continue
            frame = envelope.payload
            if not isinstance(frame, SensorFrame):
                continue
            pressure = frame.values.get("controller.pressure_supply")
            if pressure is not None:
                print("Latest pressure:", pressure)
    finally:
        subscription.close()
