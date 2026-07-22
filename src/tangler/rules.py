"""Deterministic value variation rules."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class VariationRule(BaseModel, Generic[T], ABC):
    """Abstract base class for deterministic value variations."""

    model_config = ConfigDict(frozen=True)

    @property
    @abstractmethod
    def type(self) -> type[T]:
        """Python type this rule can be applied to."""
        pass

    @abstractmethod
    def apply(self, value: T) -> T:
        """Apply the variation to a value."""
        pass


class SuffixRule(VariationRule[str]):
    """Add a suffix to a string value."""

    suffix: str

    @property
    def type(self) -> type[str]:  # noqa: D102
        return str

    def apply(self, value: str) -> str:  # noqa: D102
        return f"{value}{self.suffix}"


class PrefixRule(VariationRule[str]):
    """Add a prefix to a string value."""

    prefix: str

    @property
    def type(self) -> type[str]:  # noqa: D102
        return str

    def apply(self, value: str) -> str:  # noqa: D102
        return f"{self.prefix}{value}"


class ReplaceRule(VariationRule[str]):
    """Replace matching substrings in a string value."""

    old: str
    new: str

    @property
    def type(self) -> type[str]:  # noqa: D102
        return str

    def apply(self, value: str) -> str:  # noqa: D102
        return value.replace(self.old, self.new)
