from __future__ import annotations

from typing import Protocol

from ranger_iot.rekey import RekeySession


class RekeyProtocol(Protocol):
    """Common interface implemented by all rekeying baselines and RANGER variants."""

    def start_rekey(self, *, revoked_nodes: set[int]) -> RekeySession: ...

    def session(self, epoch: int) -> RekeySession: ...
