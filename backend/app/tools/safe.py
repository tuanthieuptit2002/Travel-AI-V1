"""Convert provider failures into structured, non-sensitive tool results."""

from __future__ import annotations

from typing import Callable, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def run_safely(call: Callable[[], T], output_type: Type[T], unavailable_message: str) -> dict:
    """Execute a tool body and never return raw provider exceptions or secrets."""
    try:
        return call().model_dump(mode="json")
    except (ValueError, LookupError):
        return output_type(success=False, error=unavailable_message).model_dump(mode="json")
    except Exception:
        # Provider messages may include operational details or credentials.
        return output_type(success=False, error=unavailable_message).model_dump(mode="json")
