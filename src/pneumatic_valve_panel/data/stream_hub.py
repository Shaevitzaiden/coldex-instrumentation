from __future__ import annotations

"""Thread-safe in-process publish/subscribe data backbone.

This module intentionally has no Qt dependency.  Device workers, recorders,
automation workers, tests, and GUI bridges can therefore all use the same hub
without requiring a Qt event loop or running in the GUI thread.

The design is inspired by ROS topics but remains lightweight:

* Producers publish immutable messages to named topics.
* Every subscription owns its own bounded queue, so consumers never steal data
  from one another as they would with one shared work queue.
* Each consumer chooses an overflow policy appropriate to its workload.
* The hub retains latest values and bounded sensor history for synchronous
  queries from anywhere in the application.
"""

import fnmatch
import queue
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from .models import CommandResult, DeviceStatus, LogEvent, SensorFrame, SensorSample


class OverflowPolicy(str, Enum):
    """What a subscription does when its private queue is full."""

    DROP_OLDEST = "drop_oldest"
    DROP_NEWEST = "drop_newest"
    REPLACE_LATEST = "replace_latest"
    BLOCK = "block"


@dataclass(frozen=True)
class StreamEnvelope:
    """Message plus routing metadata returned by subscriptions."""

    topic: str
    payload: Any
    published_monotonic_ns: int


class StreamSubscription:
    """One consumer's independent, bounded message queue."""

    def __init__(
        self,
        *,
        hub: "StreamHub",
        patterns: tuple[str, ...],
        queue_size: int,
        overflow_policy: OverflowPolicy,
        name: str,
    ) -> None:
        self._hub = hub
        self.patterns = patterns
        self.overflow_policy = overflow_policy
        self.name = name
        self._queue: queue.Queue[StreamEnvelope] = queue.Queue(maxsize=max(1, queue_size))
        self._closed = threading.Event()
        self.dropped_messages = 0

    def matches(self, topic: str) -> bool:
        return any(fnmatch.fnmatchcase(topic, pattern) for pattern in self.patterns)

    def put(self, envelope: StreamEnvelope) -> None:
        """Publish one envelope according to this subscriber's policy.

        ``BLOCK`` should be reserved for consumers such as the recorder where
        preserving every frame is more important than producer latency.  The
        default GUI policy is ``DROP_OLDEST`` so a slow redraw never stalls a
        serial device thread.
        """

        if self._closed.is_set():
            return

        if self.overflow_policy is OverflowPolicy.BLOCK:
            # A finite timeout prevents an exiting application from hanging
            # forever if a consumer has already stopped.
            try:
                self._queue.put(envelope, timeout=0.25)
            except queue.Full:
                self.dropped_messages += 1
            return

        try:
            self._queue.put_nowait(envelope)
            return
        except queue.Full:
            pass

        if self.overflow_policy is OverflowPolicy.DROP_NEWEST:
            self.dropped_messages += 1
            return

        if self.overflow_policy is OverflowPolicy.REPLACE_LATEST:
            # Drain all stale messages; only the newest state matters.
            while True:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
                else:
                    self.dropped_messages += 1
        else:  # DROP_OLDEST
            try:
                self._queue.get_nowait()
                self.dropped_messages += 1
            except queue.Empty:
                pass

        try:
            self._queue.put_nowait(envelope)
        except queue.Full:
            self.dropped_messages += 1

    def get(self, timeout: float | None = None) -> StreamEnvelope:
        if self._closed.is_set() and self._queue.empty():
            raise queue.Empty
        return self._queue.get(timeout=timeout)

    def get_nowait(self) -> StreamEnvelope:
        return self.get(timeout=0.0)

    def drain(self, max_items: int | None = None) -> list[StreamEnvelope]:
        """Return currently queued messages without blocking."""

        items: list[StreamEnvelope] = []
        while max_items is None or len(items) < max_items:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return items

    def qsize(self) -> int:
        return self._queue.qsize()

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        self._hub.unsubscribe(self)


class StreamHub:
    """Central thread-safe stream registry and pub/sub broker."""

    def __init__(
        self,
        *,
        session_origin_monotonic_ns: int | None = None,
        sensor_history_size: int = 20_000,
    ) -> None:
        self.session_origin_monotonic_ns = session_origin_monotonic_ns or time.monotonic_ns()
        self.sensor_history_size = max(1, int(sensor_history_size))
        self._lock = threading.RLock()
        self._subscriptions: set[StreamSubscription] = set()
        self._latest_by_topic: dict[str, Any] = {}
        self._latest_values: dict[str, float] = {}
        self._latest_frames: dict[str, SensorFrame] = {}
        self._sensor_history: dict[str, deque[SensorSample]] = defaultdict(
            lambda: deque(maxlen=self.sensor_history_size)
        )
        self._known_topics: set[str] = set()

    # ------------------------------------------------------------------
    # Subscription API
    # ------------------------------------------------------------------
    def subscribe(
        self,
        patterns: str | Iterable[str],
        *,
        queue_size: int = 1000,
        overflow_policy: OverflowPolicy | str = OverflowPolicy.DROP_OLDEST,
        name: str = "subscriber",
    ) -> StreamSubscription:
        normalized = (patterns,) if isinstance(patterns, str) else tuple(patterns)
        if not normalized:
            raise ValueError("At least one topic pattern is required")
        subscription = StreamSubscription(
            hub=self,
            patterns=tuple(str(pattern) for pattern in normalized),
            queue_size=queue_size,
            overflow_policy=OverflowPolicy(overflow_policy),
            name=name,
        )
        with self._lock:
            self._subscriptions.add(subscription)
        return subscription

    def unsubscribe(self, subscription: StreamSubscription) -> None:
        with self._lock:
            self._subscriptions.discard(subscription)

    # ------------------------------------------------------------------
    # Generic and typed publishing helpers
    # ------------------------------------------------------------------
    def publish(self, topic: str, payload: Any) -> None:
        envelope = StreamEnvelope(
            topic=str(topic),
            payload=payload,
            published_monotonic_ns=time.monotonic_ns(),
        )
        with self._lock:
            self._known_topics.add(envelope.topic)
            self._latest_by_topic[envelope.topic] = payload
            subscriptions = tuple(self._subscriptions)
        for subscription in subscriptions:
            if subscription.matches(envelope.topic):
                subscription.put(envelope)

    def publish_frame(self, frame: SensorFrame) -> None:
        """Publish a synchronized frame and each of its channel samples."""

        with self._lock:
            self._latest_frames[frame.source_id] = frame
            for sample in frame.samples():
                self._latest_values[sample.sensor_id] = sample.value
                self._sensor_history[sample.sensor_id].append(sample)

        self.publish(f"frames/{frame.source_id}", frame)
        for sample in frame.samples():
            # Dots remain in the sensor ID because they are convenient in YAML
            # and Python dictionaries.  Topic patterns such as ``sensors/*``
            # still match them.
            self.publish(f"sensors/{sample.sensor_id}", sample)

    def publish_log(self, event: LogEvent) -> None:
        self.publish(f"logs/{event.source}", event)

    def publish_command_result(self, result: CommandResult | dict[str, Any]) -> None:
        device_id = result.device_id if isinstance(result, CommandResult) else str(result.get("device_id", "unknown"))
        self.publish(f"commands/results/{device_id}", result)

    def publish_device_status(self, status: DeviceStatus) -> None:
        self.publish(f"devices/status/{status.device_id}", status)

    # ------------------------------------------------------------------
    # Synchronous query API available from any application component
    # ------------------------------------------------------------------
    def latest(self, topic: str, default: Any = None) -> Any:
        with self._lock:
            return self._latest_by_topic.get(topic, default)

    def latest_value(self, sensor_id: str, default: float | None = None) -> float | None:
        with self._lock:
            return self._latest_values.get(sensor_id, default)

    def latest_values(self) -> dict[str, float]:
        with self._lock:
            return dict(self._latest_values)

    def latest_frame(self, source_id: str) -> SensorFrame | None:
        with self._lock:
            return self._latest_frames.get(source_id)

    def history(
        self,
        sensor_id: str,
        *,
        start_elapsed_s: float | None = None,
        end_elapsed_s: float | None = None,
    ) -> list[SensorSample]:
        with self._lock:
            samples = list(self._sensor_history.get(sensor_id, ()))
        if start_elapsed_s is not None:
            samples = [sample for sample in samples if sample.elapsed_s >= start_elapsed_s]
        if end_elapsed_s is not None:
            samples = [sample for sample in samples if sample.elapsed_s <= end_elapsed_s]
        return samples

    def list_topics(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._known_topics))
