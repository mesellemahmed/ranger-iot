from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from ranger_iot.sim.network import Network
from ranger_iot.sim.packet import Packet, PacketFactory
from ranger_iot.sim.topology import Topology

RoutedReceiver = Callable[["RoutedMessage", int], None]


@dataclass(frozen=True, slots=True)
class RoutedMessage:
    message_id: int
    origin: int
    destination: int
    kind: str
    payload_bytes: int
    created_at_us: int
    epoch: int | None
    payload: object = None


@dataclass(frozen=True, slots=True)
class RoutedEnvelope:
    message: RoutedMessage
    path: tuple[int, ...]
    hop_index: int


class ShortestPathRouter:
    """Deterministic shortest-path unicast transport over the link-layer network."""

    PACKET_KIND_PREFIX = "route:"

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
        self._envelopes: dict[int, RoutedEnvelope] = {}
        self._receivers: dict[int, RoutedReceiver] = {}

        for node_id in topology.nodes:
            self._network.register_receiver(node_id, self._make_link_receiver(node_id))

    @property
    def now_us(self) -> int:
        return self._network.now_us

    def register_receiver(self, node_id: int, receiver: RoutedReceiver) -> None:
        if node_id not in self._topology.nodes:
            raise KeyError(f"unknown node: {node_id}")
        if node_id in self._receivers:
            raise ValueError(f"routed receiver already registered for node: {node_id}")
        self._receivers[node_id] = receiver

    def send(
        self,
        *,
        origin: int,
        destination: int,
        kind: str,
        payload_bytes: int,
        epoch: int | None = None,
        payload: object = None,
    ) -> int:
        if origin == destination:
            raise ValueError("origin and destination must differ")
        if not kind:
            raise ValueError("message kind must not be empty")
        if payload_bytes < 0:
            raise ValueError("payload_bytes must be non-negative")
        path = shortest_path(self._topology, origin, destination)
        message = RoutedMessage(
            message_id=self._next_message_id,
            origin=origin,
            destination=destination,
            kind=kind,
            payload_bytes=payload_bytes,
            created_at_us=self.now_us,
            epoch=epoch,
            payload=payload,
        )
        self._next_message_id += 1
        self._send_hop(message=message, path=path, hop_index=0)
        return message.message_id

    def _make_link_receiver(self, node_id: int) -> Callable[[Packet, int, int], None]:
        def receive(packet: Packet, sender: int, at_us: int) -> None:
            self._handle_link_delivery(node_id=node_id, packet=packet, sender=sender, at_us=at_us)

        return receive

    def _handle_link_delivery(
        self, *, node_id: int, packet: Packet, sender: int, at_us: int
    ) -> None:
        envelope = self._envelopes.pop(packet.packet_id, None)
        if envelope is None:
            raise RuntimeError(f"missing routed envelope for packet: {packet.packet_id}")

        expected_sender = envelope.path[envelope.hop_index]
        expected_receiver = envelope.path[envelope.hop_index + 1]
        if sender != expected_sender or node_id != expected_receiver:
            raise RuntimeError("routed packet delivered on an unexpected hop")

        if node_id == envelope.message.destination:
            receiver = self._receivers.get(node_id)
            if receiver is not None:
                receiver(envelope.message, at_us)
            return

        self._send_hop(
            message=envelope.message,
            path=envelope.path,
            hop_index=envelope.hop_index + 1,
        )

    def _send_hop(self, *, message: RoutedMessage, path: tuple[int, ...], hop_index: int) -> None:
        sender = path[hop_index]
        receiver = path[hop_index + 1]
        packet = self._packet_factory.create(
            source=sender,
            kind=f"{self.PACKET_KIND_PREFIX}{message.kind}",
            payload_bytes=message.payload_bytes,
            created_at_us=message.created_at_us,
            epoch=message.epoch,
        )
        self._envelopes[packet.packet_id] = RoutedEnvelope(
            message=message,
            path=path,
            hop_index=hop_index,
        )
        scheduled = self._network.send(sender=sender, receiver=receiver, packet=packet)
        if not scheduled:
            self._envelopes.pop(packet.packet_id, None)


def shortest_path(topology: Topology, source: int, destination: int) -> tuple[int, ...]:
    if source not in topology.nodes:
        raise KeyError(f"unknown source: {source}")
    if destination not in topology.nodes:
        raise KeyError(f"unknown destination: {destination}")
    if source == destination:
        return (source,)

    queue: deque[int] = deque([source])
    previous: dict[int, int | None] = {source: None}

    while queue:
        current = queue.popleft()
        for neighbor in topology.neighbors(current):
            if neighbor in previous:
                continue
            previous[neighbor] = current
            if neighbor == destination:
                return _reconstruct_path(previous, destination)
            queue.append(neighbor)

    raise ValueError(f"no route between nodes: {source} -> {destination}")


def _reconstruct_path(previous: dict[int, int | None], destination: int) -> tuple[int, ...]:
    path: list[int] = []
    current: int | None = destination
    while current is not None:
        path.append(current)
        current = previous[current]
    path.reverse()
    return tuple(path)
