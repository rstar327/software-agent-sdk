"""Docker development workspace with on-the-fly image building capability."""

from typing import Any

from pydantic import Field, model_validator

from openhands.agent_server.docker.build import (
    BuildOptions,
    TargetType,
    build,
)

from .workspace import DockerWorkspace


class DockerDevWorkspace(DockerWorkspace):
    """Docker workspace with on-the-fly image building capability.

    This workspace extends DockerWorkspace to support building Docker images
    on-the-fly from a base image. This is useful for development and testing
    scenarios where you need to customize the agent server environment.

    Note: This class requires the OpenHands SDK workspace structure and should
    only be used within the OpenHands development environment or when you have
    the full SDK source code available.

    For production use cases with pre-built images, use DockerWorkspace instead.

    Example:
        with DockerDevWorkspace(
            base_image="python:3.12",
            target="source"
        ) as workspace:
            result = workspace.execute_command("ls -la")
    """

    # Add base_image support
    base_image: str | None = Field(
        default=None,
        description=(
            "Base Docker image to build the agent server from. "
            "Mutually exclusive with server_image."
        ),
    )

    # Add build-specific options
    target: TargetType = Field(
        default="source", description="Build target for the Docker image."
    )

    @model_validator(mode="after")
    def _validate_images(self):
        """Ensure exactly one of base_image or server_image is provided."""
        if (self.base_image is None) == (self.server_image is None):
            raise ValueError(
                "Exactly one of 'base_image' or 'server_image' must be set."
            )
        if self.base_image and "ghcr.io/openhands/agent-server" in self.base_image:
            raise ValueError(
                "base_image cannot be a pre-built agent-server image. "
                "Use server_image=... instead."
            )
        return self

    def model_post_init(self, context: Any) -> None:
        """Build image if needed, then initialize the Docker container."""
        # If base_image is provided, build it first
        if self.base_image:
            # Validate platform is a valid build platform
            if self.platform not in ("linux/amd64", "linux/arm64"):
                raise ValueError(
                    f"Platform {self.platform} is not valid for building. "
                    "Must be 'linux/amd64' or 'linux/arm64'."
                )
            build_opts = BuildOptions(
                base_image=self.base_image,
                target=self.target,
                platforms=[self.platform],  # type: ignore[list-item]
                push=False,
            )
            tags = build(opts=build_opts)
            if not tags or len(tags) == 0:
                raise RuntimeError("Build failed, no image tags returned")
            # Override server_image with the built image
            object.__setattr__(self, "server_image", tags[0])

        # Now call parent's model_post_init which will use server_image
        super().model_post_init(context)
