import pytest

from ranger_iot.sim.core import EventQueue, ScheduledEvent, SimulationEngine


def test_event_queue_orders_by_time_then_sequence() -> None:
    queue = EventQueue()
    first = queue.push(at_us=10, kind="x", payload="first")
    second = queue.push(at_us=10, kind="x", payload="second")
    earlier = queue.push(at_us=5, kind="x", payload="earlier")

    assert queue.peek() == earlier
    assert queue.pop() == earlier
    assert queue.pop() == first
    assert queue.pop() == second
    assert len(queue) == 0


def test_event_queue_rejects_invalid_input() -> None:
    queue = EventQueue()
    with pytest.raises(ValueError, match="non-negative"):
        queue.push(at_us=-1, kind="x")
    with pytest.raises(ValueError, match="must not be empty"):
        queue.push(at_us=0, kind="")
    with pytest.raises(IndexError, match="empty"):
        queue.pop()


def test_engine_is_deterministic_for_equal_timestamps() -> None:
    engine = SimulationEngine()
    observed: list[str] = []

    def handler(event: ScheduledEvent) -> None:
        observed.append(str(event.payload))

    engine.register_handler("record", handler)
    engine.schedule_after(10, "record", "a")
    engine.schedule_after(10, "record", "b")
    engine.schedule_at(5, "record", "c")

    assert engine.run() == 3
    assert observed == ["c", "a", "b"]
    assert engine.now_us == 10
    assert engine.processed_events == 3
    assert engine.pending_events == 0


def test_engine_run_limits_and_guards() -> None:
    engine = SimulationEngine()
    observed: list[int] = []
    engine.register_handler("record", lambda event: observed.append(event.at_us))
    engine.schedule_at(5, "record")
    engine.schedule_at(10, "record")

    assert engine.run(until_us=5) == 1
    assert observed == [5]
    assert engine.pending_events == 1
    assert engine.run(max_events=0) == 0
    assert engine.run(max_events=1) == 1
    assert observed == [5, 10]

    with pytest.raises(ValueError, match="earlier"):
        engine.run(until_us=9)
    with pytest.raises(ValueError, match="non-negative"):
        engine.run(max_events=-1)
    with pytest.raises(ValueError, match="past"):
        engine.schedule_at(9, "record")
    with pytest.raises(ValueError, match="non-negative"):
        engine.schedule_after(-1, "record")


def test_engine_rejects_duplicate_and_missing_handlers() -> None:
    engine = SimulationEngine()
    engine.register_handler("known", lambda event: None)

    with pytest.raises(ValueError, match="already registered"):
        engine.register_handler("known", lambda event: None)
    with pytest.raises(ValueError, match="must not be empty"):
        engine.register_handler("", lambda event: None)

    engine.schedule_at(0, "unknown")
    with pytest.raises(RuntimeError, match="no handler"):
        engine.run()
