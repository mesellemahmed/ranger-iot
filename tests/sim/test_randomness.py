import pytest

from ranger_iot.sim.randomness import RandomStream


def test_random_stream_replays_exact_sequence() -> None:
    left = RandomStream(42, "loss")
    right = RandomStream(42, "loss")

    assert left.derived_seed == right.derived_seed
    assert [left.random() for _ in range(5)] == [right.random() for _ in range(5)]


def test_forked_streams_are_namespace_isolated() -> None:
    root = RandomStream(7)
    loss = root.fork("loss")
    delay = root.fork("delay")
    loss_replay = RandomStream(7).fork("loss")

    assert loss.namespace == "root/loss"
    assert loss.derived_seed != delay.derived_seed
    assert [loss.random() for _ in range(3)] == [loss_replay.random() for _ in range(3)]


def test_random_stream_helpers_and_validation() -> None:
    rng = RandomStream(3)

    assert 1.0 <= rng.uniform(1.0, 2.0) <= 2.0
    assert 2 <= rng.integer(2, 5) < 5
    assert rng.master_seed == 3

    with pytest.raises(ValueError, match="master_seed"):
        RandomStream(-1)
    with pytest.raises(ValueError, match="namespace"):
        RandomStream(1, "")
    with pytest.raises(ValueError, match="namespace"):
        rng.fork("")
    with pytest.raises(ValueError, match="greater"):
        rng.uniform(2.0, 1.0)
    with pytest.raises(ValueError, match="greater"):
        rng.integer(3, 3)
