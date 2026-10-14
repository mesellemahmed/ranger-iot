from __future__ import annotations

from collections.abc import Iterable
from itertools import pairwise
from math import isqrt
from typing import Literal

from ranger_iot.sim.topology import StaticTopology

TopologyName = Literal["line", "star", "balanced-tree", "grid"]


def build_topology(
    name: TopologyName,
    *,
    nodes: Iterable[int],
    root_id: int,
) -> StaticTopology:
    """Build a deterministic connected topology rooted at ``root_id``."""

    ordered = _root_first_nodes(nodes, root_id=root_id)

    if name == "line":
        edges = tuple(pairwise(ordered))
    elif name == "star":
        edges = tuple((root_id, node_id) for node_id in ordered[1:])
    elif name == "balanced-tree":
        edges = _balanced_tree_edges(ordered)
    elif name == "grid":
        edges = _grid_edges(ordered)
    else:
        raise ValueError(f"unsupported topology: {name}")

    return StaticTopology.from_edges(nodes=ordered, edges=edges)


def _root_first_nodes(nodes: Iterable[int], *, root_id: int) -> tuple[int, ...]:
    supplied = tuple(nodes)
    if not supplied:
        raise ValueError("topology must contain at least one node")
    if len(set(supplied)) != len(supplied):
        raise ValueError("topology node identifiers must be unique")
    if root_id not in supplied:
        raise ValueError(f"root node is outside the topology: {root_id}")

    return (root_id, *sorted(node_id for node_id in supplied if node_id != root_id))


def _balanced_tree_edges(nodes: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    return tuple(
        (nodes[(child_index - 1) // 2], nodes[child_index]) for child_index in range(1, len(nodes))
    )


def _grid_edges(nodes: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    width = isqrt(len(nodes) - 1) + 1
    edges: list[tuple[int, int]] = []

    for index, node_id in enumerate(nodes):
        column = index % width
        right_index = index + 1
        down_index = index + width

        if column + 1 < width and right_index < len(nodes):
            edges.append((node_id, nodes[right_index]))
        if down_index < len(nodes):
            edges.append((node_id, nodes[down_index]))

    return tuple(edges)
