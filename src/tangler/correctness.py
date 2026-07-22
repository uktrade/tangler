"""Correctness helpers for comparing generated entities with resolved output."""

from collections import Counter
from collections.abc import Iterable

import polars as pl

from tangler._graph import DisjointSet
from tangler.entities import ClusterEntity, EntityReference
from tangler.types import SourceName


def query_to_cluster_entities(
    data: pl.DataFrame,
    keys: dict[SourceName, str],
) -> set[ClusterEntity]:
    """Convert resolved query output to cluster entities.

    Args:
        data: Polars DataFrame containing an `id` column and source key columns.
        keys: Mapping of source names to key field names.

    Returns:
        A set of cluster entities grouped by `id`.
    """
    must_have_fields = set(["id"] + list(keys.values()))
    if not must_have_fields.issubset(data.columns):
        raise ValueError(
            f"Fields {must_have_fields.difference(data.columns)} must be included "
            "in the data and are missing."
        )

    grouped = data.group_by("id").agg(
        pl.col(key_field).drop_nulls().unique().alias(source)
        for source, key_field in keys.items()
    )

    entities: set[ClusterEntity] = set()
    for row in grouped.iter_rows(named=True):
        entity_refs: dict[SourceName, frozenset[str]] = {}
        for source in keys:
            source_keys = row[source]
            if source_keys:
                entity_refs[source] = frozenset(source_keys)

        entities.add(
            ClusterEntity(
                id=row["id"],
                keys=EntityReference(entity_refs),
            )
        )

    return entities


def _merge_cluster_entities(
    entities: Iterable[ClusterEntity],
) -> ClusterEntity | None:
    """Merge cluster entities without relying on sum's integer start value."""
    iterator = iter(entities)
    merged = next(iterator, None)
    if merged is None:
        return None
    for entity in iterator:
        merged += entity
    return merged


def scores_to_results_entities(
    scores: pl.DataFrame,
    left_clusters: tuple[ClusterEntity, ...],
    right_clusters: tuple[ClusterEntity, ...] | None = None,
    threshold: float = 0.0,
) -> tuple[ClusterEntity, ...]:
    """Convert scored pairwise links to merged cluster entities."""
    left_lookup = {entity.id: entity for entity in left_clusters}
    if right_clusters is not None:
        right_lookup = {entity.id: entity for entity in right_clusters}
    else:
        right_lookup = left_lookup

    djs = DisjointSet[ClusterEntity]()

    for entity in left_clusters:
        djs.add(entity)
    if right_clusters is not None:
        for entity in right_clusters:
            djs.add(entity)

    for record in scores.to_dicts():
        if record["score"] >= threshold:
            djs.union(
                left_lookup[record["left_id"]],
                right_lookup[record["right_id"]],
            )

    entities: list[ClusterEntity] = []
    for component in djs.get_components():
        merged = _merge_cluster_entities(component)
        if merged is not None:
            entities.append(merged)

    return tuple(entities)


def diff_entities(
    expected: list[ClusterEntity], actual: list[ClusterEntity]
) -> tuple[bool, dict[str, int]]:
    """Compare expected and actual cluster entities.

    Args:
        expected: True cluster entities.
        actual: Resolved cluster entities produced by a user workflow.

    Returns:
        A tuple of whether the sets match exactly and a count report for imperfect
        matches. The report keys are `perfect`, `subset`, `superset`, `wrong`,
        and `invalid`.
    """
    expected_set, actual_set = set(expected), set(actual)
    if expected_set == actual_set:
        return True, {}

    all_expected = _merge_cluster_entities(expected_set)
    perfect_matches = expected_set & actual_set
    remaining_actual = actual_set - perfect_matches

    counter = Counter(
        {
            "perfect": len(perfect_matches),
            "subset": 0,
            "superset": 0,
            "wrong": 0,
            "invalid": 0,
        }
    )

    for actual_entity in remaining_actual:
        if any(actual_entity in expected_entity for expected_entity in expected_set):
            counter["subset"] += 1
        elif all_expected is None or actual_entity not in all_expected:
            counter["invalid"] += 1
        elif any(expected_entity in actual_entity for expected_entity in expected_set):
            counter["superset"] += 1
        else:
            counter["wrong"] += 1

    return False, dict(counter)
