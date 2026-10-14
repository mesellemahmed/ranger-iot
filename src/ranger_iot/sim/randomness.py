from __future__ import annotations

import hashlib

import numpy as np


class RandomStream:
    """Deterministic, namespace-isolated PCG64 random stream."""

    def __init__(self, master_seed: int, namespace: str = "root") -> None:
        if master_seed < 0:
            raise ValueError("master_seed must be non-negative")
        if not namespace:
            raise ValueError("namespace must not be empty")

        self._master_seed = master_seed
        self._namespace = namespace
        self._derived_seed = self._derive_seed(master_seed, namespace)
        self._generator = np.random.Generator(np.random.PCG64(self._derived_seed))

    @staticmethod
    def _derive_seed(master_seed: int, namespace: str) -> int:
        material = f"{master_seed}:{namespace}".encode()
        digest = hashlib.blake2b(material, digest_size=16).digest()
        return int.from_bytes(digest, byteorder="big", signed=False)

    @property
    def master_seed(self) -> int:
        return self._master_seed

    @property
    def namespace(self) -> str:
        return self._namespace

    @property
    def derived_seed(self) -> int:
        return self._derived_seed

    def fork(self, namespace: str) -> RandomStream:
        if not namespace:
            raise ValueError("namespace must not be empty")
        return RandomStream(self._master_seed, f"{self._namespace}/{namespace}")

    def random(self) -> float:
        return float(self._generator.random())

    def uniform(self, low: float, high: float) -> float:
        if high < low:
            raise ValueError("high must be greater than or equal to low")
        return float(self._generator.uniform(low, high))

    def integer(self, low: int, high: int) -> int:
        if high <= low:
            raise ValueError("high must be greater than low")
        return int(self._generator.integers(low, high))
