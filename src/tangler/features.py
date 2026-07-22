"""Feature generation configuration."""

from typing import Self

import polars as pl
from faker import Faker
from pydantic import BaseModel, ConfigDict, Field, field_validator

from tangler.rules import VariationRule


def infer_data_type(base: str, parameters: tuple | None) -> pl.DataType:
    """Infer a Polars type from a Faker provider configuration.

    Args:
        base: Faker provider name.
        parameters: Parameters passed to the provider.

    Returns:
        A Polars data type inferred from sample generated values.
    """
    generator = Faker()
    value_generator = getattr(generator, base)
    generator_kwargs = {} if not parameters else dict(parameters)
    examples = [value_generator(**generator_kwargs) for _ in range(5)]
    series = pl.Series(examples)
    return series.dtype


class FeatureConfig(BaseModel):
    """Configuration for generating a feature value."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: str
    base_generator: str
    parameters: tuple | None = Field(
        default=None,
        description=(
            "Parameters for the generator. A tuple of tuples passed to the generator."
        ),
    )
    unique: bool = Field(
        default=True,
        description=(
            "Whether the generator enforces uniqueness in the generated data. "
            "For example, using unique=True with the 'boolean' generator will error "
            "if more the two values are generated."
        ),
    )
    drop_base: bool = Field(
        default=False, description="Whether the base case is dropped."
    )
    variations: tuple[VariationRule, ...] = Field(default_factory=tuple)
    datatype: pl.DataType = Field(
        default_factory=lambda data: infer_data_type(
            data["base_generator"], data["parameters"]
        )
    )

    def add_variations(self, *rule: VariationRule) -> "FeatureConfig":
        """Return a copy with additional variation rules."""
        return FeatureConfig(
            name=self.name,
            base_generator=self.base_generator,
            parameters=self.parameters,
            unique=self.unique,
            drop_base=self.drop_base,
            variations=self.variations + tuple(rule),
        )

    @field_validator("name", mode="after")
    @classmethod
    def protected_names(cls: type[Self], value: str) -> str:
        """Ensure feature names do not collide with generated record metadata."""
        if value in {"id", "key"}:
            raise ValueError("Feature name cannot be 'id' or 'key'.")
        return value
