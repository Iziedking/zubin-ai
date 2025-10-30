"""Storage configuration schema."""

from typing import Optional
from pydantic.dataclasses import dataclass
from pydantic import Field, field_validator


@dataclass
class PostgresConfig:
    """PostgreSQL persistence configuration for execution traces and checkpoints."""

    enabled: bool = Field(
        default=False,
        description="Enable PostgreSQL persistence for traces and checkpoints"
    )

    connection_url: str = Field(
        default="postgresql+asyncpg://localhost/roma_dspy",
        description="PostgreSQL connection URL using asyncpg driver"
    )

    pool_size: int = Field(
        default=5,
        description="Connection pool size",
        ge=1,
        le=50
    )

    max_overflow: int = Field(
        default=10,
        description="Maximum overflow connections beyond pool_size",
        ge=0,
        le=100
    )

    pool_timeout: float = Field(
        default=30.0,
        description="Connection pool timeout in seconds",
        ge=1.0
    )

    echo_sql: bool = Field(
        default=False,
        description="Echo SQL statements to logs (debug mode)"
    )

    @field_validator("connection_url")
    @classmethod
    def validate_connection_url(cls, v: str) -> str:
        """Validate connection URL uses asyncpg driver."""
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("connection_url must use asyncpg driver (postgresql+asyncpg://)")
        return v


@dataclass
class StorageConfig:
    """
    Storage configuration for execution-scoped file storage.

    The base_path is where S3 is mounted via goofys in production,
    or a local directory in development. It should be the same across
    all environments (host, Docker, E2B) for path consistency.
    """

    base_path: str = Field(
        description=(
            "Base storage path (mount point for S3 via goofys). "
            "This path must be identical across host and E2B for file sharing. "
            "Set via STORAGE_BASE_PATH environment variable."
        ),
        examples=["~/.tmp/sentient", "${HOME}/roma_storage"]
    )

    max_file_size: int = Field(
        default=100 * 1024 * 1024,
        description="Maximum file size in bytes (default: 100MB)",
        ge=0
    )

    buffer_size: int = Field(
        default=1024 * 1024,
        description=(
            "I/O buffer size in bytes for goofys optimization (default: 1MB). "
            "Larger buffers reduce small writes that goofys handles poorly."
        ),
        ge=1024
    )

    postgres: Optional[PostgresConfig] = Field(
        default=None,
        description="PostgreSQL persistence configuration"
    )