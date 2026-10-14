from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class Topology(Protocol):
    @property
    def nodes(self) -> tuple[int, ...]: ...

    def neighbors(self, node_id: int) -> tuple[int, ...]: ...

    def has_link(self, left: int, right: int) -> bool: ...


class StaticTopology:
    """Immutable undirected topology with deterministic neighbor ordering."""

    def __init__(self, adjacency: dict[int, tuple[int, ...]]) -> None:
        self._adjacency = adjacency
        self._nodes = tuple(sorted(adjacency))

    @classmethod
    def from_edges(
        cls,
        nodes: Iterable[int],
        edges: Iterable[tuple[int, int]],
    ) -> StaticTopology:
        node_set = set(nodes)
        if not node_set:
            raise ValueError("topology must contain at least one node")
        if any(node_id < 0 for node_id in node_set):
            raise ValueError("node identifiers must be non-negative")

        adjacency: dict[int, set[int]] = {node_id: set() for node_id in node_set}
        for left, right in edges:
            if left == right:
                raise ValueError("self-links are not allowed")
            if left not in adjacency or right not in adjacency:
                raise ValueError("edge references an unknown node")
            adjacency[left].add(right)
            adjacency[right].add(left)

        frozen = {node_id: tuple(sorted(neighbors)) for node_id, neighbors in adjacency.items()}
        return cls(frozen)

    @property
    def nodes(self) -> tuple[int, ...]:
        return self._nodes

    def neighbors(self, node_id: int) -> tuple[int, ...]:
        try:
            return self._adjacency[node_id]
        except KeyError as exc:
            raise KeyError(f"unknown node: {node_id}") from exc

    def has_link(self, left: int, right: int) -> bool:
        if left not in self._adjacency or right not in self._adjacency:
            return False
        return right in self._adjacency[left]
