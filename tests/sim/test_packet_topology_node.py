import pytest

from ranger_iot.sim.node import NodeRegistry
from ranger_iot.sim.packet import Packet, PacketFactory
from ranger_iot.sim.topology import StaticTopology


def test_packet_factory_allocates_monotonic_ids() -> None:
    factory = PacketFactory()
    first = factory.create(source=0, kind="hello", payload_bytes=10, created_at_us=0)
    second = factory.create(source=0, kind="rekey", payload_bytes=20, created_at_us=1, epoch=2)

    assert first.packet_id == 0
    assert second.packet_id == 1
    assert second.epoch == 2


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"packet_id": -1, "source": 0, "kind": "x", "payload_bytes": 0, "created_at_us": 0},
            "packet_id",
        ),
        (
            {"packet_id": 0, "source": -1, "kind": "x", "payload_bytes": 0, "created_at_us": 0},
            "source",
        ),
        ({"packet_id": 0, "source": 0, "kind": "", "payload_bytes": 0, "created_at_us": 0}, "kind"),
        (
            {"packet_id": 0, "source": 0, "kind": "x", "payload_bytes": -1, "created_at_us": 0},
            "payload_bytes",
        ),
        (
            {"packet_id": 0, "source": 0, "kind": "x", "payload_bytes": 0, "created_at_us": -1},
            "created_at_us",
        ),
        (
            {
                "packet_id": 0,
                "source": 0,
                "kind": "x",
                "payload_bytes": 0,
                "created_at_us": 0,
                "epoch": -1,
            },
            "epoch",
        ),
    ],
)
def test_packet_validation(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Packet(**kwargs)  # type: ignore[arg-type]


def test_static_topology_is_undirected_and_sorted() -> None:
    topology = StaticTopology.from_edges(nodes=[2, 0, 1], edges=[(0, 2), (0, 1)])

    assert topology.nodes == (0, 1, 2)
    assert topology.neighbors(0) == (1, 2)
    assert topology.neighbors(1) == (0,)
    assert topology.has_link(2, 0)
    assert not topology.has_link(1, 2)
    assert not topology.has_link(9, 0)

    with pytest.raises(KeyError, match="unknown node"):
        topology.neighbors(9)


def test_static_topology_validation() -> None:
    with pytest.raises(ValueError, match="at least one"):
        StaticTopology.from_edges(nodes=[], edges=[])
    with pytest.raises(ValueError, match="non-negative"):
        StaticTopology.from_edges(nodes=[-1], edges=[])
    with pytest.raises(ValueError, match="self-links"):
        StaticTopology.from_edges(nodes=[0], edges=[(0, 0)])
    with pytest.raises(ValueError, match="unknown node"):
        StaticTopology.from_edges(nodes=[0], edges=[(0, 1)])


def test_node_registry_tracks_activity() -> None:
    registry = NodeRegistry([2, 0, 1])

    assert registry.ids == (0, 1, 2)
    assert registry.active_ids == (0, 1, 2)
    assert registry.contains(1)
    assert registry.is_active(1)

    registry.set_active(1, False)
    assert not registry.is_active(1)
    assert registry.active_ids == (0, 2)

    with pytest.raises(ValueError, match="already registered"):
        registry.add(0)
    with pytest.raises(ValueError, match="non-negative"):
        registry.add(-1)
    with pytest.raises(KeyError, match="unknown node"):
        registry.set_active(9, False)
