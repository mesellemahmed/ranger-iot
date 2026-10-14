from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ranger_iot.sim.network import Network
from ranger_iot.sim.packet import Packet, PacketFactory
from ranger_iot.sim.topology import Topology


@dataclass(frozen=True, slots=True)
class FloodMessage:
    """One application message disseminated by deterministic graph flooding."""

    message_id: int
    origin: int
    kind: str
    payload_bytes: int
    created_at_us: int
    epoch: int | None
    payload: object = None


FloodReceiver = Callable[[FloodMessage, int], None]


class FloodTransport:
    """Deterministic first-seen flooding with duplicate suppression.

    Each node forwards a flood message at most once, after its first successful
    reception. The ingress neighbor is excluded from the immediate forwarding
    set, while duplicates arriving over alternate paths are suppressed by the
    message identifier. Each forwarding action is one one-to-many radio broadcast;
    receiver-specific link attempts remain available as a separate metric.
    """

    PACKET_KIND_PREFIX = "flood:"

    def __init__(
        self,
        *,
        network: Network,
        topology: Topology,
        packet_factory: PacketFactory,
    ) -> None:
        self._network = network
        self._topology = topology
        self._packet_factory = packet_factory
        self._next_message_id = 0
        self._frames: dict[int, FloodMessage] = {}
        self._direct_frames: dict[int, FloodMessage] = {}
        self._seen: dict[int, set[int]] = {node_id: set() for node_id in topology.nodes}
        self._receivers: dict[int, FloodReceiver] = {}

        for node_id in topology.nodes:
            self._network.register_receiver(node_id, self._make_link_receiver(node_id))

    @property
    def now_us(self) -> int:
        return self._network.now_us

    def neighbors(self, node_id: int) -> tuple[int, ...]:
        if node_id not in self._topology.nodes:
            raise KeyError(f"unknown node: {node_id}")
        return self._topology.neighbors(node_id)

    def register_receiver(self, node_id: int, receiver: FloodReceiver) -> None:
        if node_id not in self._topology.nodes:
            raise KeyError(f"unknown node: {node_id}")
        if node_id in self._receivers:
            raise ValueError(f"flood receiver already registered for node: {node_id}")
        self._receivers[node_id] = receiver

    def flood(
        self,
        *,
        origin: int,
        kind: str,
        payload_bytes: int,
        epoch: int | None = None,
        payload: object = None,
    ) -> int:
        if origin not in self._topology.nodes:
            raise KeyError(f"unknown origin: {origin}")
        if not kind:
            raise ValueError("message kind must not be empty")
        if payload_bytes < 0:
            raise ValueError("payload_bytes must be non-negative")

        message = FloodMessage(
            message_id=self._next_message_id,
            origin=origin,
            kind=kind,
            payload_bytes=payload_bytes,
            created_at_us=self.now_us,
            epoch=epoch,
            payload=payload,
        )
        self._next_message_id += 1
        self._seen[origin].add(message.message_id)

        receiver = self._receivers.get(origin)
        if receiver is not None:
            receiver(message, self.now_us)

        self._forward(node_id=origin, ingress=None, message=message)
        return message.message_id

    def send_neighbor(
        self,
        *,
        origin: int,
        destination: int,
        kind: str,
        payload_bytes: int,
        epoch: int | None = None,
        payload: object = None,
    ) -> int:
        """Send one non-forwarded control/data message to a direct neighbor."""

        if origin not in self._topology.nodes:
            raise KeyError(f"unknown origin: {origin}")
        if destination not in self._topology.nodes:
            raise KeyError(f"unknown destination: {destination}")
        if not self._topology.has_link(origin, destination):
            raise ValueError(f"nodes are not direct neighbors: {origin} -> {destination}")
        if not kind:
            raise ValueError("message kind must not be empty")
        if payload_bytes < 0:
            raise ValueError("payload_bytes must be non-negative")

        message = FloodMessage(
            message_id=self._next_message_id,
            origin=origin,
            kind=kind,
            payload_bytes=payload_bytes,
            created_at_us=self.now_us,
            epoch=epoch,
            payload=payload,
        )
        self._next_message_id += 1
        packet = self._packet_factory.create(
            source=origin,
            kind=f"direct:{kind}",
            payload_bytes=payload_bytes,
            created_at_us=message.created_at_us,
            epoch=epoch,
        )
        self._direct_frames[packet.packet_id] = message
        scheduled = self._network.send(sender=origin, receiver=destination, packet=packet)
        if not scheduled:
            self._direct_frames.pop(packet.packet_id, None)
        return message.message_id

    def _make_link_receiver(self, node_id: int) -> Callable[[Packet, int, int], None]:
        def receive(packet: Packet, sender: int, at_us: int) -> None:
            self._handle_link_delivery(
                node_id=node_id,
                packet=packet,
                sender=sender,
                at_us=at_us,
            )

        return receive

    def _handle_link_delivery(
        self,
        *,
        node_id: int,
        packet: Packet,
        sender: int,
        at_us: int,
    ) -> None:
        direct_message = self._direct_frames.pop(packet.packet_id, None)
        if direct_message is not None:
            receiver = self._receivers.get(node_id)
            if receiver is not None:
                receiver(direct_message, at_us)
            return

        message = self._frames.get(packet.packet_id)
        if message is None:
            raise RuntimeError(f"missing flood message for packet: {packet.packet_id}")

        seen = self._seen[node_id]
        if message.message_id in seen:
            return
        seen.add(message.message_id)

        receiver = self._receivers.get(node_id)
        if receiver is not None:
            receiver(message, at_us)

        self._forward(node_id=node_id, ingress=sender, message=message)

    def _forward(self, *, node_id: int, ingress: int | None, message: FloodMessage) -> None:
        packet = self._packet_factory.create(
            source=node_id,
            kind=f"{self.PACKET_KIND_PREFIX}{message.kind}",
            payload_bytes=message.payload_bytes,
            created_at_us=message.created_at_us,
            epoch=message.epoch,
        )
        self._frames[packet.packet_id] = message
        self._network.broadcast(
            sender=node_id,
            packet=packet,
            exclude=ingress,
        )
