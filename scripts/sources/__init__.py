"""Independent international Danube source adapters."""

from .registry import ADAPTERS, get_adapter

__all__ = ["ADAPTERS", "get_adapter"]
