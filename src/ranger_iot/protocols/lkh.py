from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class LkhKeyRef:
    """Symbolic reference to one LKH key version."""

    node_id: int
    version: int

    def __post_init__(self) -> None:
        if self.node_id <= 0:
            raise ValueError("node_id must be positive")
        if self.version < 0:
            raise ValueError("version must be non-negative")


@dataclass(frozen=True, slots=True)
class LkhKeyUpdate:
    """One logical LKH ciphertext carrying a replacement key."""

    target: LkhKeyRef
    wrapper: LkhKeyRef
    recipients: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.recipients:
            raise ValueError("recipients must not be empty")
        if len(set(self.recipients)) != len(self.recipients):
            raise ValueError("recipients must be unique")
        if any(member_id < 0 for member_id in self.recipients):
            raise ValueError("recipient identifiers must be non-negative")


@dataclass(frozen=True, slots=True)
class LkhRekeyPlan:
    """Deterministic bottom-up key-update plan for one LKH rekey operation."""

    revoked_members: tuple[int, ...]
    affected_nodes: tuple[int, ...]
    updates: tuple[LkhKeyUpdate, ...]
    root_key: LkhKeyRef

    @property
    def logical_ciphertexts(self) -> int:
        return len(self.updates)


class LkhKeyTree:
    """Balanced binary Logical Key Hierarchy with symbolic key versions.

    Leaves are individual member keys. Internal nodes are key-encryption keys,
    with node 1 representing the group key. Cryptographic operations are modeled
    symbolically; this class plans which key versions must be replaced and under
    which child keys the replacements are protected.
    """

    ROOT_NODE = 1

    def __init__(self, member_ids: set[int]) -> None:
        if len(member_ids) < 2:
            raise ValueError("LKH requires at least two members")
        if any(member_id < 0 for member_id in member_ids):
            raise ValueError("member identifiers must be non-negative")

        self._member_ids = tuple(sorted(member_ids))
        self._active_members = set(member_ids)
        self._leaf_base = 1 << math.ceil(math.log2(len(member_ids)))
        self._member_to_leaf = {
            member_id: self._leaf_base + offset for offset, member_id in enumerate(self._member_ids)
        }
        self._leaf_to_member = {leaf: member for member, leaf in self._member_to_leaf.items()}
        self._versions = {node_id: 0 for node_id in range(1, 2 * self._leaf_base)}
        self._members_under_cache: dict[int, tuple[int, ...]] = {}

    @property
    def member_ids(self) -> tuple[int, ...]:
        return self._member_ids

    @property
    def active_member_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self._active_members))

    @property
    def leaf_base(self) -> int:
        return self._leaf_base

    @property
    def root_key(self) -> LkhKeyRef:
        return self.key_ref(self.ROOT_NODE)

    def leaf_node(self, member_id: int) -> int:
        try:
            return self._member_to_leaf[member_id]
        except KeyError as exc:
            raise KeyError(f"unknown LKH member: {member_id}") from exc

    def key_ref(self, node_id: int) -> LkhKeyRef:
        self._require_tree_node(node_id)
        return LkhKeyRef(node_id=node_id, version=self._versions[node_id])

    def member_key_path(self, member_id: int) -> tuple[int, ...]:
        node_id = self.leaf_node(member_id)
        path: list[int] = []
        while node_id >= self.ROOT_NODE:
            path.append(node_id)
            if node_id == self.ROOT_NODE:
                break
            node_id //= 2
        return tuple(path)

    def members_under(self, node_id: int, *, active_only: bool = False) -> tuple[int, ...]:
        self._require_tree_node(node_id)
        members = self._members_under_node(node_id)
        if active_only:
            members = tuple(member for member in members if member in self._active_members)
        return members

    def rekey(self, revoked_members: set[int]) -> LkhRekeyPlan:
        self._validate_revocations(revoked_members)
        active_after = self._active_members - revoked_members
        if not active_after:
            raise ValueError("LKH rekey cannot revoke all active members")

        affected_nodes = self._affected_internal_nodes(revoked_members, active_after)
        next_versions = {node_id: self._versions[node_id] + 1 for node_id in affected_nodes}

        updates: list[LkhKeyUpdate] = []
        for target_node in affected_nodes:
            target_ref = LkhKeyRef(target_node, next_versions[target_node])
            for child_node in self._children(target_node):
                recipients = tuple(
                    member
                    for member in self._members_under_node(child_node)
                    if member in active_after
                )
                if not recipients:
                    continue

                wrapper_version = next_versions.get(child_node, self._versions[child_node])
                updates.append(
                    LkhKeyUpdate(
                        target=target_ref,
                        wrapper=LkhKeyRef(child_node, wrapper_version),
                        recipients=recipients,
                    )
                )

        for node_id, version in next_versions.items():
            self._versions[node_id] = version
        self._active_members = active_after

        return LkhRekeyPlan(
            revoked_members=tuple(sorted(revoked_members)),
            affected_nodes=affected_nodes,
            updates=tuple(updates),
            root_key=self.root_key,
        )

    def _validate_revocations(self, revoked_members: set[int]) -> None:
        unknown = revoked_members - set(self._member_ids)
        if unknown:
            raise KeyError(f"unknown LKH member: {min(unknown)}")
        already_revoked = revoked_members - self._active_members
        if already_revoked:
            raise ValueError(f"member already revoked: {min(already_revoked)}")

    def _affected_internal_nodes(
        self,
        revoked_members: set[int],
        active_after: set[int],
    ) -> tuple[int, ...]:
        if not revoked_members:
            return (self.ROOT_NODE,)

        affected: set[int] = set()
        for member_id in revoked_members:
            node_id = self.leaf_node(member_id) // 2
            while node_id >= self.ROOT_NODE:
                if any(member in active_after for member in self._members_under_node(node_id)):
                    affected.add(node_id)
                if node_id == self.ROOT_NODE:
                    break
                node_id //= 2

        return tuple(sorted(affected, key=lambda node: (-self._depth(node), node)))

    def _members_under_node(self, node_id: int) -> tuple[int, ...]:
        cached = self._members_under_cache.get(node_id)
        if cached is not None:
            return cached

        members: tuple[int, ...]

        if node_id >= self._leaf_base:
            member = self._leaf_to_member.get(node_id)
            members = () if member is None else (member,)
        else:
            left, right = self._children(node_id)
            members = tuple(
                sorted(
                    (
                        *self._members_under_node(left),
                        *self._members_under_node(right),
                    )
                )
            )

        self._members_under_cache[node_id] = members
        return members

    def _children(self, node_id: int) -> tuple[int, int]:
        if node_id >= self._leaf_base:
            raise ValueError("leaf nodes do not have children")
        return (2 * node_id, 2 * node_id + 1)

    @staticmethod
    def _depth(node_id: int) -> int:
        return node_id.bit_length() - 1

    def _require_tree_node(self, node_id: int) -> None:
        if node_id not in self._versions:
            raise KeyError(f"unknown LKH tree node: {node_id}")
