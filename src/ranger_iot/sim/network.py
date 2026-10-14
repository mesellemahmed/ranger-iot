from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ranger_iot.sim.core import ScheduledEvent, SimulationEngine
from ranger_iot.sim.delay import DelayModel
from ranger_iot.sim.loss import LossModel
from ranger_iot.sim.metrics import DropReason, NetworkObserver
from ranger_iot.sim.node import NodeRegistry
from ranger_iot.sim.packet import Packet
from ranger_iot.sim.randomness import RandomStream
from ranger_iot.sim.topology import Topology

PacketReceiver = Callable[[Packet, int, int], None]


@dataclass(frozen=True, slots=True)
class PendingDelivery:
    sender: int
    receiver: int
    packet: Packet


class Network:
    """Deterministic link-layer abstraction for protocol experiments."""

    DELIVERY_EVENT = "network.delivery"

    def __init__(
        self,
        *,
        engine: SimulationEngine,
        topology: Topology,
        nodes: NodeRegistry,
        loss_model: LossModel,
        delay_model: DelayModel,
        rng: RandomStream,
        observers: Iterable[NetworkObserver] = (),
    ) -> None:
        if set(topology.nodes) != set(nodes.ids):
            raise ValueError("topology and node registry must contain the same node identifiers")

        self._engine = engine
        self._topology = topology
        self._nodes = nodes
        self._loss_model = loss_model
        self._delay_model = delay_model
        self._rng = rng
        self._observers = tuple(observers)
        self._receivers: dict[int, PacketReceiver] = {}
        self._engine.register_handler(self.DELIVERY_EVENT, self._handle_delivery)

    @property
    def now_us(self) -> int:
        return self._engine.now_us

    def register_receiver(self, node_id: int, receiver: PacketReceiver) -> None:
        if not self._nodes.contains(node_id):
            raise KeyError(f"unknown node: {node_id}")
        if node_id in self._receivers:
            raise ValueError(f"receiver already registered for node: {node_id}")
        self._receivers[node_id] = receiver

    def send(self, *, sender: int, receiver: int, packet: Packet) -> bool:
        """Send one unicast link frame."""

        self._validate_send(sender=sender, receiver=receiver, packet=packet)
        self._notify_radio_transmit(sender=sender, packet=packet)
        return self._attempt_delivery(sender=sender, receiver=receiver, packet=packet)

    def broadcast(
        self,
        *,
        sender: int,
        packet: Packet,
        exclude: int | None = None,
    ) -> int:
        """Emit one one-to-many radio broadcast.

        Loss and delivery remain receiver-specific, while radio accounting
        counts exactly one sender-side emission.
        """

        if not self._nodes.contains(sender):
            raise KeyError(f"unknown sender: {sender}")
        if not self._nodes.is_active(sender):
            raise RuntimeError(f"inactive node cannot transmit: {sender}")
        if packet.source != sender:
            raise ValueError("packet source does not match sender")
        if exclude is not None and not self._nodes.contains(exclude):
            raise KeyError(f"unknown excluded node: {exclude}")

        receivers = tuple(
            receiver for receiver in self._topology.neighbors(sender) if receiver != exclude
        )
        if not receivers:
            return 0

        self._notify_radio_transmit(sender=sender, packet=packet)
        scheduled = 0
        for receiver in receivers:
            scheduled += int(
                self._attempt_delivery(
                    sender=sender,
                    receiver=receiver,
                    packet=packet,
                )
            )
        return scheduled

    def _attempt_delivery(self, *, sender: int, receiver: int, packet: Packet) -> bool:
        """Perform one receiver-specific link attempt without radio recounting."""

        self._notify_transmit(sender=sender, receiver=receiver, packet=packet)

        if not self._nodes.is_active(receiver):
            self._notify_drop(
                sender=sender,
                receiver=receiver,
                packet=packet,
                reason=DropReason.RECEIVER_INACTIVE,
            )
            return False

        if self._loss_model.should_drop(
            sender=sender,
            receiver=receiver,
            packet=packet,
            rng=self._rng,
        ):
            self._notify_drop(
                sender=sender,
                receiver=receiver,
                packet=packet,
                reason=DropReason.LOSS_MODEL,
            )
            return False

        delay_us = self._delay_model.delay_us(
            sender=sender,
            receiver=receiver,
            packet=packet,
            rng=self._rng,
        )
        self._engine.schedule_after(
            delay_us,
            self.DELIVERY_EVENT,
            PendingDelivery(sender=sender, receiver=receiver, packet=packet),
        )
        return True

    def _validate_send(self, *, sender: int, receiver: int, packet: Packet) -> None:
        if not self._nodes.contains(sender):
            raise KeyError(f"unknown sender: {sender}")
        if not self._nodes.contains(receiver):
            raise KeyError(f"unknown receiver: {receiver}")
        if not self._nodes.is_active(sender):
            raise RuntimeError(f"inactive node cannot transmit: {sender}")
        if sender == receiver:
            raise ValueError("sender and receiver must differ")
        if packet.source != sender:
            raise ValueError("packet source does not match sender")
        if not self._topology.has_link(sender, receiver):
            raise ValueError(f"nodes are not directly connected: {sender} -> {receiver}")

    def _handle_delivery(self, event: ScheduledEvent) -> None:
        payload = event.payload
        if not isinstance(payload, PendingDelivery):
            raise TypeError("invalid network delivery payload")

        if not self._nodes.is_active(payload.receiver):
            self._notify_drop(
                sender=payload.sender,
                receiver=payload.receiver,
                packet=payload.packet,
                reason=DropReason.RECEIVER_INACTIVE,
            )
            return

        for observer in self._observers:
            observer.on_deliver(
                at_us=self._engine.now_us,
                sender=payload.sender,
                receiver=payload.receiver,
                packet=payload.packet,
            )

        receiver = self._receivers.get(payload.receiver)
        if receiver is not None:
            receiver(payload.packet, payload.sender, self._engine.now_us)

    def _notify_radio_transmit(self, *, sender: int, packet: Packet) -> None:
        for observer in self._observers:
            callback = getattr(observer, "on_radio_transmit", None)
            if callback is not None:
                callback(
                    at_us=self._engine.now_us,
                    sender=sender,
                    packet=packet,
                )

    def _notify_transmit(self, *, sender: int, receiver: int, packet: Packet) -> None:
        for observer in self._observers:
            observer.on_transmit(
                at_us=self._engine.now_us,
                sender=sender,
                receiver=receiver,
                packet=packet,
            )

    def _notify_drop(
        self,
        *,
        sender: int,
        receiver: int,
        packet: Packet,
        reason: DropReason,
    ) -> None:
        for observer in self._observers:
            observer.on_drop(
                at_us=self._engine.now_us,
                sender=sender,
                receiver=receiver,
                packet=packet,
                reason=reason,
            )
