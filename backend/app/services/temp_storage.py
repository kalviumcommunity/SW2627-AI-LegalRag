"""Secure temporary storage for uploaded documents.

Files are written to an OS-created temporary file with a randomized name (never
the client filename). The file is always removed, including when extraction or
chunking raises.
"""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.services.ingestion_errors import DocumentStorageError


@contextmanager
def secure_temp_file(
    data: bytes, suffix: str, directory: str | None = None
) -> Iterator[Path]:
    """Yield a private temporary path, then delete it reliably."""
    target_dir: str | None = None
    if directory:
        try:
            target_path = Path(directory)
            target_path.mkdir(parents=True, exist_ok=True)
            target_dir = str(target_path)
        except OSError as exc:
            raise DocumentStorageError(
                "Secure temporary storage is unavailable."
            ) from exc

    path: str | None = None
    try:
        try:
            file_descriptor, path = tempfile.mkstemp(
                prefix="property_ingest_", suffix=suffix, dir=target_dir
            )
            with os.fdopen(file_descriptor, "wb") as handle:
                handle.write(data)
        except OSError as exc:
            raise DocumentStorageError(
                "Secure temporary storage is unavailable."
            ) from exc
        yield Path(path)
    finally:
        if path is not None:
            try:
                os.unlink(path)
            except OSError:
                # Cleanup must never mask the original processing result.
                pass
