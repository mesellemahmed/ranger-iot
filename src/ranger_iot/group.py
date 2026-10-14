from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MemberState:
    node_id: int
    current_epoch: int = 0
    revoked: bool = False

    def __post_init__(self) -> None:
        if self.node_id < 0:
            raise ValueError("node_id must be non-negative")
        if self.current_epoch < 0:
            raise ValueError("current_epoch must be non-negative")


class GroupState:
    """Authoritative membership and epoch state for one group."""

    def __init__(
        self,
        *,
        group_id: int,
        manager_id: int,
        member_ids: set[int],
        initial_epoch: int = 0,
    ) -> None:
        if group_id < 0:
            raise ValueError("group_id must be non-negative")
        if manager_id < 0:
            raise ValueError("manager_id must be non-negative")
        if initial_epoch < 0:
            raise ValueError("initial_epoch must be non-negative")
        if not member_ids:
            raise ValueError("group must contain at least one member")
        if manager_id in member_ids:
            raise ValueError("manager must not be included in member_ids")
        if any(node_id < 0 for node_id in member_ids):
            raise ValueError("member identifiers must be non-negative")

        self.group_id = group_id
        self.manager_id = manager_id
        self.current_epoch = initial_epoch
        self._members = {
            node_id: MemberState(node_id=node_id, current_epoch=initial_epoch)
            for node_id in sorted(member_ids)
        }

    @property
    def member_ids(self) -> tuple[int, ...]:
        return tuple(self._members)

    @property
    def authorized_member_ids(self) -> tuple[int, ...]:
        return tuple(node_id for node_id, state in self._members.items() if not state.revoked)

    @property
    def revoked_member_ids(self) -> tuple[int, ...]:
        return tuple(node_id for node_id, state in self._members.items() if state.revoked)

    def is_authorized(self, node_id: int) -> bool:
        return not self._require_member(node_id).revoked

    def member_epoch(self, node_id: int) -> int:
        return self._require_member(node_id).current_epoch

    def revoke(self, node_id: int) -> None:
        state = self._require_member(node_id)
        if state.revoked:
            raise ValueError(f"member already revoked: {node_id}")
        state.revoked = True

    def advance_epoch(self) -> int:
        self.current_epoch += 1
        return self.current_epoch

    def accept_epoch(self, node_id: int, epoch: int) -> bool:
        state = self._require_member(node_id)
        if state.revoked:
            return False
        if epoch <= state.current_epoch:
            return False
        if epoch > self.current_epoch:
            raise ValueError(
                "member cannot accept an epoch newer than the authoritative group epoch"
            )
        state.current_epoch = epoch
        return True

    def convergence_fraction(self, epoch: int | None = None) -> float:
        target_epoch = self.current_epoch if epoch is None else epoch
        authorized = self.authorized_member_ids
        if not authorized:
            return 1.0
        synchronized = sum(self.member_epoch(node_id) >= target_epoch for node_id in authorized)
        return synchronized / len(authorized)

    def _require_member(self, node_id: int) -> MemberState:
        try:
            return self._members[node_id]
        except KeyError as exc:
            raise KeyError(f"unknown group member: {node_id}") from exc
