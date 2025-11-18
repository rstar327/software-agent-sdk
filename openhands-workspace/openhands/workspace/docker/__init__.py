"""Docker workspace implementation."""

from .workspace import DockerWorkspace


__all__ = ["DockerWorkspace", "DockerDevWorkspace"]


def __getattr__(name: str):
    """Lazy import DockerDevWorkspace to avoid build module imports."""
    if name == "DockerDevWorkspace":
        from .dev_workspace import DockerDevWorkspace

        return DockerDevWorkspace
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
