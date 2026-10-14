from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(slots=True)
class NodeRecord:
    node_id: int
    active: bool = True


class NodeRegistry:
    """Mutable runtime state for nodes participating in one simulation."""

    def __init__(self, node_ids: Iterable[int] = ()) -> None:
        self._nodes: dict[int, NodeRecord] = {}
        for node_id in node_ids:
            self.add(node_id)

    @property
    def ids(self) -> tuple[int, ...]:
        return tuple(sorted(self._nodes))

    @property
    def active_ids(self) -> tuple[int, ...]:
        return tuple(sorted(node_id for node_id, node in self._nodes.items() if node.active))

    def add(self, node_id: int) -> None:
        if node_id < 0:
            raise ValueError("node_id must be non-negative")
        if node_id in self._nodes:
            raise ValueError(f"node already registered: {node_id}")
        self._nodes[node_id] = NodeRecord(node_id=node_id)

    def contains(self, node_id: int) -> bool:
        return node_id in self._nodes

    def is_active(self, node_id: int) -> bool:
        return self._require(node_id).active

    def set_active(self, node_id: int, active: bool) -> None:
        self._require(node_id).active = active

    def _require(self, node_id: int) -> NodeRecord:
        try:
            return self._nodes[node_id]
        except KeyError as exc:
            raise KeyError(f"unknown node: {node_id}") from exc
