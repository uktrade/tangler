"""Entity generation helpers."""

from functools import cache
from typing import Any

from faker import Faker

from tangler.entities import EntityReference, SourceEntity
from tangler.features import FeatureConfig


@cache
def generate_entities(
    generator: Faker,
    features: tuple[FeatureConfig, ...],
    n: int,
) -> tuple[SourceEntity, ...]:
    """Generate base entities with their ground-truth feature values."""
    entities: list[SourceEntity] = []
    for _ in range(n):
        base_values: dict[str, Any] = {}
        for feature in features:
            generator_func = generator.unique if feature.unique else generator
            value_generator = getattr(generator_func, feature.base_generator)
            parameters = {} if not feature.parameters else dict(feature.parameters)

            value = value_generator(**parameters)
            if isinstance(value, list):
                value = tuple(value)
            base_values[feature.name] = value

        entities.append(SourceEntity(base_values=base_values, keys=EntityReference()))
    return tuple(entities)
