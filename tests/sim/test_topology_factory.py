import pytest

from ranger_iot.sim.routing import shortest_path
from ranger_iot.sim.topology_factory import build_topology


def test_line_topology_places_root_at_one_end() -> None:
    topology = build_topology("line", nodes=(7, 1, 2, 3), root_id=7)

    assert topology.nodes == (1, 2, 3, 7)
    assert shortest_path(topology, 7, 3) == (7, 1, 2, 3)


def test_star_topology_connects_every_node_directly_to_root() -> None:
    topology = build_topology("star", nodes=(0, 1, 2, 3, 4), root_id=0)

    assert topology.neighbors(0) == (1, 2, 3, 4)
    assert shortest_path(topology, 0, 4) == (0, 4)
    assert shortest_path(topology, 1, 4) == (1, 0, 4)


def test_balanced_tree_is_breadth_first_and_deterministic() -> None:
    topology = build_topology("balanced-tree", nodes=range(7), root_id=0)

    assert topology.neighbors(0) == (1, 2)
    assert topology.neighbors(1) == (0, 3, 4)
    assert topology.neighbors(2) == (0, 5, 6)
    assert shortest_path(topology, 0, 6) == (0, 2, 6)


def test_grid_uses_near_square_row_major_layout() -> None:
    topology = build_topology("grid", nodes=range(9), root_id=0)

    assert topology.neighbors(0) == (1, 3)
    assert topology.neighbors(4) == (1, 3, 5, 7)
    assert topology.neighbors(8) == (5, 7)
    assert shortest_path(topology, 0, 8) == (0, 1, 2, 5, 8)


def test_partial_grid_remains_connected() -> None:
    topology = build_topology("grid", nodes=range(5), root_id=0)

    assert shortest_path(topology, 0, 4) == (0, 1, 4)


def test_topology_factory_validates_root_and_node_identifiers() -> None:
    with pytest.raises(ValueError, match="at least one"):
        build_topology("line", nodes=(), root_id=0)
    with pytest.raises(ValueError, match="must be unique"):
        build_topology("line", nodes=(0, 1, 1), root_id=0)
    with pytest.raises(ValueError, match="outside the topology"):
        build_topology("line", nodes=(0, 1), root_id=9)
