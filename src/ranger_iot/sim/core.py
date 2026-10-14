from __future__ import annotations

import heapq
from collections.abc import Callable
from dataclasses import dataclass, field

EventHandler = Callable[["ScheduledEvent"], None]


@dataclass(order=True, frozen=True, slots=True)
class ScheduledEvent:
    """A deterministic discrete-event simulation event."""

    at_us: int
    sequence: int
    kind: str = field(compare=False)
    payload: object = field(default=None, compare=False)


class EventQueue:
    """Priority queue ordered by simulation time and insertion sequence."""

    def __init__(self) -> None:
        self._events: list[ScheduledEvent] = []
        self._next_sequence = 0

    def __len__(self) -> int:
        return len(self._events)

    def push(self, *, at_us: int, kind: str, payload: object = None) -> ScheduledEvent:
        if at_us < 0:
            raise ValueError("event time must be non-negative")
        if not kind:
            raise ValueError("event kind must not be empty")

        event = ScheduledEvent(
            at_us=at_us,
            sequence=self._next_sequence,
            kind=kind,
            payload=payload,
        )
        self._next_sequence += 1
        heapq.heappush(self._events, event)
        return event

    def peek(self) -> ScheduledEvent | None:
        return self._events[0] if self._events else None

    def pop(self) -> ScheduledEvent:
        if not self._events:
            raise IndexError("cannot pop from an empty event queue")
        return heapq.heappop(self._events)


class SimulationEngine:
    """Single-threaded deterministic discrete-event engine."""

    def __init__(self) -> None:
        self._queue = EventQueue()
        self._handlers: dict[str, EventHandler] = {}
        self._now_us = 0
        self._processed_events = 0

    @property
    def now_us(self) -> int:
        return self._now_us

    @property
    def processed_events(self) -> int:
        return self._processed_events

    @property
    def pending_events(self) -> int:
        return len(self._queue)

    def register_handler(self, kind: str, handler: EventHandler) -> None:
        if not kind:
            raise ValueError("event kind must not be empty")
        if kind in self._handlers:
            raise ValueError(f"handler already registered for event kind: {kind}")
        self._handlers[kind] = handler

    def schedule_at(self, at_us: int, kind: str, payload: object = None) -> ScheduledEvent:
        if at_us < self._now_us:
            raise ValueError("cannot schedule an event in the past")
        return self._queue.push(at_us=at_us, kind=kind, payload=payload)

    def schedule_after(self, delay_us: int, kind: str, payload: object = None) -> ScheduledEvent:
        if delay_us < 0:
            raise ValueError("event delay must be non-negative")
        return self.schedule_at(self._now_us + delay_us, kind, payload)

    def run(self, *, until_us: int | None = None, max_events: int | None = None) -> int:
        if until_us is not None and until_us < self._now_us:
            raise ValueError("until_us cannot be earlier than the current simulation time")
        if max_events is not None and max_events < 0:
            raise ValueError("max_events must be non-negative")

        processed = 0
        while self._queue:
            if max_events is not None and processed >= max_events:
                break

            next_event = self._queue.peek()
            if next_event is None:
                break
            if until_us is not None and next_event.at_us > until_us:
                break

            event = self._queue.pop()
            handler = self._handlers.get(event.kind)
            if handler is None:
                raise RuntimeError(f"no handler registered for event kind: {event.kind}")

            self._now_us = event.at_us
            handler(event)
            processed += 1
            self._processed_events += 1

        return processed
