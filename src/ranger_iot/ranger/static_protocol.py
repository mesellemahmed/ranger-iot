from __future__ import annotations

from dataclasses import dataclass, field

from ranger_iot.group import GroupState
from ranger_iot.protocols.lkh import LkhKeyTree, LkhRekeyPlan
from ranger_iot.ranger.capsule import RekeyCapsule
from ranger_iot.ranger.coding import (
    CodedFragment,
    CodingParameters,
    FragmentAccumulator,
    StaticErasureCoder,
)
from ranger_iot.rekey import RekeySession
from ranger_iot.sim.flooding import FloodMessage, FloodReceiver, FloodTransport


@dataclass(frozen=True, slots=True)
class RangerStaticParameters:
    """Fixed coding profile and capsule-size model for RANGER-STATIC."""

    coding: CodingParameters = field(
        default_factory=lambda: CodingParameters(data_fragments=3, total_fragments=5)
    )
    ciphertext_payload_bytes: int = 64
    capsule_overhead_bytes: int = 0

    def __post_init__(self) -> None:
        if self.ciphertext_payload_bytes <= 0:
            raise ValueError("ciphertext_payload_bytes must be positive")
        if self.capsule_overhead_bytes < 0:
            raise ValueError("capsule_overhead_bytes must be non-negative")


@dataclass(frozen=True, slots=True)
class RangerStaticStats:
    """Protocol-level counters for one RANGER-STATIC rekey epoch."""

    epoch: int
    logical_ciphertexts: int
    capsule_payload_bytes: int
    data_fragments: int
    total_fragments: int
    fragment_payload_bytes: int
    flood_injections: int


@dataclass(slots=True)
class _RangerStaticEpochState:
    plan: LkhRekeyPlan
    capsule: RekeyCapsule
    fragments: tuple[CodedFragment, ...]
    session: RekeySession
    accumulators: dict[int, FragmentAccumulator]
    flood_injections: int = 0


class RangerStaticProtocol:
    """Static coded dissemination of one opaque LKH rekey capsule.

    LKH remains the authorization mechanism.  RANGER aggregates the complete
    encrypted LKH rekey plan into one opaque capsule, models ideal k-of-n MDS
    coding, and floods every coded fragment once.  An authorized member accepts
    the new epoch after receiving any ``k`` distinct fragments.

    This stage intentionally has no retry, neighbor recovery, self-healing, or
    adaptive coding.  Revoked nodes may still relay fragments at the network
    layer but are never allowed to accept the new group epoch.
    """

    MESSAGE_KIND = "ranger.static.fragment"

    def __init__(
        self,
        *,
        group: GroupState,
        tree: LkhKeyTree,
        transport: FloodTransport,
        parameters: RangerStaticParameters | None = None,
    ) -> None:
        if set(group.member_ids) != set(tree.member_ids):
            raise ValueError("group and LKH tree must contain the same members")
        if group.current_epoch != tree.root_key.version:
            raise ValueError("group epoch and LKH root-key version must match")

        self._group = group
        self._tree = tree
        self._transport = transport
        self._parameters = parameters or RangerStaticParameters()
        self._epochs: dict[int, _RangerStaticEpochState] = {}

        for member_id in group.member_ids:
            self._transport.register_receiver(member_id, self._make_member_receiver(member_id))

    @property
    def sessions(self) -> tuple[RekeySession, ...]:
        return tuple(self._epochs[epoch].session for epoch in sorted(self._epochs))

    def session(self, epoch: int) -> RekeySession:
        return self._require_epoch(epoch).session

    def plan(self, epoch: int) -> LkhRekeyPlan:
        return self._require_epoch(epoch).plan

    def capsule(self, epoch: int) -> RekeyCapsule:
        return self._require_epoch(epoch).capsule

    def fragments(self, epoch: int) -> tuple[CodedFragment, ...]:
        return self._require_epoch(epoch).fragments

    def transport_stats(self, epoch: int) -> RangerStaticStats:
        state = self._require_epoch(epoch)
        first_fragment = state.fragments[0]
        return RangerStaticStats(
            epoch=epoch,
            logical_ciphertexts=state.plan.logical_ciphertexts,
            capsule_payload_bytes=state.capsule.payload_bytes,
            data_fragments=first_fragment.data_fragments,
            total_fragments=first_fragment.total_fragments,
            fragment_payload_bytes=first_fragment.payload_bytes,
            flood_injections=state.flood_injections,
        )

    def start_rekey(self, *, revoked_nodes: set[int]) -> RekeySession:
        self._validate_group_revocations(revoked_nodes)
        plan = self._tree.rekey(revoked_nodes)

        for node_id in sorted(revoked_nodes):
            self._group.revoke(node_id)

        epoch = self._group.advance_epoch()
        if epoch != plan.root_key.version:
            raise RuntimeError("LKH root-key version diverged from group epoch")

        targets = self._group.authorized_member_ids
        session = RekeySession(epoch=epoch, started_at_us=self._transport.now_us, targets=targets)

        capsule_payload_bytes = (
            plan.logical_ciphertexts * self._parameters.ciphertext_payload_bytes
            + self._parameters.capsule_overhead_bytes
        )
        capsule = RekeyCapsule(
            capsule_id=f"group-{self._group.group_id}-epoch-{epoch}",
            group_id=self._group.group_id,
            epoch=epoch,
            logical_ciphertexts=plan.logical_ciphertexts,
            payload_bytes=capsule_payload_bytes,
        )
        fragments = StaticErasureCoder.encode(capsule, self._parameters.coding)
        accumulators = {
            member_id: FragmentAccumulator(
                capsule_id=capsule.capsule_id,
                group_id=capsule.group_id,
                epoch=capsule.epoch,
                parameters=self._parameters.coding,
            )
            for member_id in targets
        }
        state = _RangerStaticEpochState(
            plan=plan,
            capsule=capsule,
            fragments=fragments,
            session=session,
            accumulators=accumulators,
        )
        self._epochs[epoch] = state

        for fragment in self._initial_fragments(fragments):
            self._flood_fragment(state, fragment)

        return session

    def _initial_fragments(self, fragments: tuple[CodedFragment, ...]) -> tuple[CodedFragment, ...]:
        return fragments

    def _flood_fragment(self, state: _RangerStaticEpochState, fragment: CodedFragment) -> None:
        self._transport.flood(
            origin=self._group.manager_id,
            kind=self.MESSAGE_KIND,
            payload_bytes=fragment.payload_bytes,
            epoch=fragment.epoch,
            payload=fragment,
        )
        state.flood_injections += 1

    def _make_member_receiver(self, member_id: int) -> FloodReceiver:
        def receive(message: FloodMessage, at_us: int) -> None:
            self._handle_fragment(member_id=member_id, flooded=message, at_us=at_us)

        return receive

    def _handle_fragment(self, *, member_id: int, flooded: FloodMessage, at_us: int) -> None:
        if flooded.kind != self.MESSAGE_KIND:
            return

        fragment = flooded.payload
        if not isinstance(fragment, CodedFragment):
            raise TypeError("invalid RANGER coded-fragment payload")
        if flooded.epoch != fragment.epoch:
            raise ValueError("flood epoch does not match coded-fragment epoch")
        self._accept_fragment(member_id=member_id, fragment=fragment, at_us=at_us)

    def _accept_fragment(
        self,
        *,
        member_id: int,
        fragment: CodedFragment,
        at_us: int,
    ) -> bool:
        if fragment.group_id != self._group.group_id:
            return False
        if not self._group.is_authorized(member_id):
            return False

        state = self._epochs.get(fragment.epoch)
        if state is None:
            return False

        accumulator = state.accumulators[member_id]
        if not accumulator.accept(fragment):
            return False
        if not accumulator.decodable:
            return False

        accepted = self._group.accept_epoch(member_id, fragment.epoch)
        if accepted:
            state.session.record_acceptance(member_id, at_us)
        return accepted

    def _validate_group_revocations(self, revoked_nodes: set[int]) -> None:
        members = set(self._group.member_ids)
        unknown = revoked_nodes - members
        if unknown:
            raise KeyError(f"unknown group member: {min(unknown)}")

        already_revoked = {
            node_id for node_id in revoked_nodes if not self._group.is_authorized(node_id)
        }
        if already_revoked:
            raise ValueError(f"member already revoked: {min(already_revoked)}")

    def _require_epoch(self, epoch: int) -> _RangerStaticEpochState:
        try:
            return self._epochs[epoch]
        except KeyError as exc:
            raise KeyError(f"unknown rekey epoch: {epoch}") from exc
