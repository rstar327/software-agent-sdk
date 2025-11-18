"""OpenHands Workspace - Docker and container-based workspace implementations."""

from .docker import DockerWorkspace
from .remote_api import APIRemoteWorkspace


__all__ = [
    "DockerWorkspace",
    "DockerDevWorkspace",
    "APIRemoteWorkspace",
]


def __getattr__(name: str):
    """Lazy import DockerDevWorkspace to avoid build module imports."""
    if name == "DockerDevWorkspace":
        from .docker import DockerDevWorkspace

        return DockerDevWorkspace
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
