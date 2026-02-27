"""Core / service layer — pure business logic and data transformations.

Rules
-----
* No ``print()`` calls.
* No filesystem or network I/O.
* No imports from ``cli`` or ``infra``.
* All functions must be fully typed and deterministic.
"""

from ytd_wrap.core.download_service import DownloadService
from ytd_wrap.core.metadata_service import MetadataService
from ytd_wrap.core.models import FormatCollection, VideoFormat, VideoMetadata
from ytd_wrap.core.protocols import DownloadProvider, MetadataProvider

__all__: list[str] = [
    "DownloadProvider",
    "DownloadService",
    "FormatCollection",
    "MetadataProvider",
    "MetadataService",
    "VideoFormat",
    "VideoMetadata",
]
