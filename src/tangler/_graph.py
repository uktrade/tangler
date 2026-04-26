"""Internal graph utilities."""

from collections import defaultdict
from collections.abc import Hashable
from typing import Generic, TypeVar

T = TypeVar("T", bound=Hashable)


class DisjointSet(Generic[T]):
    """Disjoint-set forest with path compression and union by rank."""

    def __init__(self) -> None:
        """Initialize the disjoint set."""
        self.parent: dict[T, T] = {}
        self.rank: dict[T, int] = {}

    def _make_set(self, x: T) -> None:
        """Create a new set with a single element."""
        self.parent[x] = x
        self.rank[x] = 0

    def add(self, x: T) -> None:
        """Add a new element to the disjoint set."""
        if x not in self.parent:
            self._make_set(x)

    def union(self, x: T, y: T) -> None:
        """Merge the sets containing two elements."""
        self._link(self._find(x), self._find(y))

    def _link(self, x: T, y: T) -> None:
        """Merge two representative elements."""
        if self.rank[x] > self.rank[y]:
            self.parent[y] = x
        else:
            self.parent[x] = y
            if self.rank[x] == self.rank[y]:
                self.rank[y] += 1

    def _find(self, x: T) -> T:
        """Return the representative element of the set containing an element."""
        if x not in self.parent:
            self._make_set(x)
            return x

        if x != self.parent[x]:
            self.parent[x] = self._find(self.parent[x])

        return self.parent[x]

    def get_components(self) -> list[set[T]]:
        """Return connected components from the disjoint set."""
        components = defaultdict(set)
        for x in self.parent:
            root = self._find(x)
            components[root].add(x)
        return list(components.values())
