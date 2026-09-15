"""Stable, provider-agnostic travel data interfaces and implementations."""

__all__ = ["build_tool_dependencies"]


def __getattr__(name: str):
    if name == "build_tool_dependencies":
        from app.providers.factory import build_tool_dependencies

        return build_tool_dependencies
    raise AttributeError(name)
