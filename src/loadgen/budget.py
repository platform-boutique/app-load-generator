"""Hard caps shared by all simulated users of one run (single process, gevent: no locking needed)."""

from __future__ import annotations


class Budget:
    """At most `limit` successful uses per run. take() reserves one, give_back() releases it again."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.used = 0

    def take(self) -> bool:
        if self.used >= self.limit:
            return False
        self.used += 1
        return True

    def give_back(self) -> None:
        self.used = max(0, self.used - 1)

    @property
    def exhausted(self) -> bool:
        return self.used >= self.limit
