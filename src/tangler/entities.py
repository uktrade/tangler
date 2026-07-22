"""Ground-truth entity objects and source references."""

from collections.abc import Iterator, Mapping
from random import getrandbits
from types import NotImplementedType
from typing import Any

import polars as pl
from pydantic import BaseModel, ConfigDict, Field

from tangler.types import SourceName

SourceData = Any


class EntityReference(Mapping[SourceName, frozenset[str]]):
    """Reference to an entity's presence in specific sources.

    Maps source names to sets of primary keys.
    """

    def __init__(
        self,
        mapping: Mapping[SourceName, frozenset[str]] | None = None,
    ) -> None:
        """Initialise the EntityReference."""
        self._mapping = dict({} if mapping is None else mapping)

    def __getitem__(self, key: SourceName) -> frozenset[str]:
        """Return the key set for a source."""
        return self._mapping[key]

    def __iter__(self) -> Iterator[SourceName]:
        """Iterate over source names."""
        return iter(self._mapping)

    def __len__(self) -> int:
        """Return the number of source references."""
        return len(self._mapping)

    def __hash__(self) -> int:
        """Hash based on source names and their key sets."""
        return hash(
            tuple(
                (source, tuple(sorted(keys)))
                for source, keys in sorted(self._mapping.items())
            )
        )

    def __add__(self, other: "EntityReference") -> "EntityReference":
        """Merge two EntityReferences by unioning keys for each source."""
        if not isinstance(other, EntityReference):
            raise TypeError(
                "EntityReference can only be added to another EntityReference."
            )

        return EntityReference(
            {
                k: self.get(k, frozenset()) | other.get(k, frozenset())
                for k in self.keys() | other.keys()
            }
        )

    def __le__(self, other: object) -> bool:
        """Test if self is a subset of other."""
        if not isinstance(other, EntityReference):
            return False

        return all(name in other and self[name] <= other[name] for name in self)


class EntityIDMixin:
    """Mixin providing integer ID comparisons for entity classes."""

    id: int

    def __int__(self) -> int:
        """Allow converting an entity to an integer by returning its ID."""
        return self.id

    def __lt__(self, other: object) -> bool | NotImplementedType:
        """Compare based on ID for sorting operations."""
        if isinstance(other, EntityIDMixin):
            return self.id < other.id
        if isinstance(other, int):
            return self.id < other
        return NotImplemented

    def __gt__(self, other: object) -> bool | NotImplementedType:
        """Compare based on ID for sorting operations."""
        if isinstance(other, EntityIDMixin):
            return self.id > other.id
        if isinstance(other, int):
            return self.id > other
        return NotImplemented

    def __le__(self, other: object) -> bool | NotImplementedType:
        """Compare based on ID for sorting operations."""
        if isinstance(other, EntityIDMixin):
            return self.id <= other.id
        if isinstance(other, int):
            return self.id <= other
        return NotImplemented

    def __ge__(self, other: object) -> bool | NotImplementedType:
        """Compare based on ID for sorting operations."""
        if isinstance(other, EntityIDMixin):
            return self.id >= other.id
        if isinstance(other, int):
            return self.id >= other
        return NotImplemented


class SourceKeyMixin:
    """Mixin providing source key lookup helpers for entity classes."""

    keys: EntityReference

    def get_keys(self, name: SourceName) -> set[str]:
        """Get keys for a specific source.

        Args:
            name: Name of the source

        Returns:
            Set of keys, empty if source not found
        """
        return set(self.keys.get(name, frozenset()))

    def get_values(
        self, sources: dict[SourceName, SourceData]
    ) -> dict[SourceName, dict[str, list[str]]]:
        """Get all unique values for this entity across sources.

        Each source may have its own variations/transformations of the base data,
        so we maintain separation between sources.

        Args:
            sources: Dictionary of source name to source data.

        Returns:
            Dictionary mapping:
                source_name -> {
                    feature_name -> [unique values for that feature in that source]
                }
        """
        values: dict[str, dict[str, list[str]]] = {}

        # For each source we have keys for
        for source_name, keys in self.keys.items():
            source = sources.get(source_name)

            if source is None:
                raise ValueError(f"Source data not found: {source_name}")

            # Get rows for this entity in this source
            entity_rows = source.data.filter(pl.col("key").is_in(list(keys)))

            # Get unique values for each feature in this source
            values[source_name] = {
                feature.name: sorted(
                    entity_rows.get_column(feature.name).unique().drop_nulls().to_list()
                )
                for feature in source.features
            }

        return values


class ClusterEntity(BaseModel, EntityIDMixin, SourceKeyMixin):
    """Represents one resolved cluster across one or more sources."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    id: int = Field(default_factory=lambda: getrandbits(63))  # 64 gives OverflowError
    keys: EntityReference

    def __add__(self, other: "ClusterEntity") -> "ClusterEntity":
        """Combine two ClusterEntity objects by combining the keys."""
        if other is None:
            return self
        if not isinstance(other, ClusterEntity):
            return NotImplemented
        return ClusterEntity(keys=self.keys + other.keys)

    def __radd__(self, other: object) -> "ClusterEntity":
        """Handle sum() by treating 0 as an empty ClusterEntity."""
        if other == 0:  # sum() starts with 0
            return self
        return NotImplemented

    def __sub__(self, other: "ClusterEntity") -> dict[str, frozenset[str]]:
        """Return keys in self that aren't in other, by source.

        Used to diff two ClusterEntity objects.
        """
        if not isinstance(other, ClusterEntity):
            return NotImplemented

        diff = {}
        for name, our_keys in self.keys.items():
            their_keys = other.keys.get(name, frozenset())
            if remaining := our_keys - their_keys:
                diff[name] = remaining

        return diff

    def __rsub__(self, other: "ClusterEntity") -> dict[str, frozenset[str]]:
        """Support reverse subtraction."""
        if not isinstance(other, ClusterEntity):
            return NotImplemented
        return other - self

    def __eq__(self, other: object) -> bool:
        """Compare based on keys."""
        if not isinstance(other, ClusterEntity):
            return NotImplemented
        return self.keys == other.keys

    def __contains__(self, other: "ClusterEntity") -> bool:
        """Check if this entity contains all keys from other entity."""
        return other.keys <= self.keys

    def __hash__(self) -> int:
        """Hash based on EntityReference which is itself hashable."""
        return hash(self.keys)

    def is_subset_of_source_entity(self, source_entity: "SourceEntity") -> bool:
        """Check if this ClusterEntity's references are a subset of a SourceEntity's."""
        return self.keys <= source_entity.keys

    def similarity_ratio(self, other: "ClusterEntity") -> float:
        """Return ratio of shared keys to total keys across all sources."""
        total_keys = 0
        shared_keys = 0

        # Get all source names
        all_sources = set(self.keys.keys()) | set(other.keys.keys())

        for name in all_sources:
            our_keys = self.keys.get(name, frozenset())
            their_keys = other.keys.get(name, frozenset())

            total_keys += len(our_keys | their_keys)
            shared_keys += len(our_keys & their_keys)

        return shared_keys / total_keys if total_keys > 0 else 0.0


class SourceEntity(BaseModel, EntityIDMixin, SourceKeyMixin):
    """Represents one ground-truth entity across sources."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: int = Field(default_factory=lambda: getrandbits(63))  # 64 gives OverflowError
    base_values: dict[str, Any] = Field(description="Feature name -> base value")
    keys: EntityReference = Field(
        description="Source to keys mapping",
        default_factory=EntityReference,
    )
    total_unique_variations: int = Field(default=0)

    def __eq__(self, other: object) -> bool:
        """Equal if base values are shared, or integer ID matches."""
        if isinstance(other, SourceEntity):
            return self.base_values == other.base_values
        if isinstance(other, int):
            return self.id == other
        return NotImplemented

    def __hash__(self) -> int:
        """Hash based on sorted base values."""
        return hash(tuple(sorted(self.base_values.items())))

    def add_source_reference(self, name: SourceName, keys: list[str]) -> None:
        """Add or update a source reference.

        Args:
            name: Source name
            keys: List of primary keys for this source
        """
        mapping = dict(self.keys)
        mapping[name] = frozenset(keys)
        self.keys = EntityReference(mapping)

    def to_cluster_entity(self, *names: SourceName) -> ClusterEntity | None:
        """Convert this SourceEntity to a ClusterEntity with the specified sources.

        This method makes diffing really easy. Testing whether ClusterEntity objects
        are subsets of SourceEntity objects is a weaker, logically more fragile test
        than directly comparing equality of sets of ClusterEntity objects. It enables
        a really simple syntactical expression of the test.

        ```python
        actual: set[ClusterEntity] = ...
        expected: set[ClusterEntity] = {
            s.to_cluster_entity("source1", "source2")
            for s in source_entities
        }

        is_identical = expected) == actual
        missing = expected - actual
        extra = actual - expected
        ```

        Args:
            *names: Names of sources to include in the ClusterEntity

        Returns:
            ClusterEntity containing only the specified sources' keys, or None
            if none of the specified sources are present in this entity.
        """
        filtered: dict[SourceName, frozenset[str]] = {}
        for name in names:
            keys = self.keys.get(name)
            if keys is not None:
                filtered[name] = keys

        if len(filtered) == 0:
            return None

        return ClusterEntity(keys=EntityReference(filtered))
