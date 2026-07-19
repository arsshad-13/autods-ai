"""
Dataset service — all upload, retrieval, and deletion business logic lives here.

Security properties enforced:
- Extension whitelist (.csv, .xlsx, .xls)
- MIME type whitelist
- 100 MB hard cap (checked before writing to disk)
- Original filename is sanitised (no path separators, null bytes, etc.)
- Stored filename is a UUID — no user input ever touches the filesystem path
- Files are written only inside settings.UPLOAD_DIR
- Ownership is enforced on every read / delete operation
"""

import logging
import os
import re
import unicodedata
import uuid as uuid_module
from uuid import UUID
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.dataset import Dataset

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".csv", ".xlsx", ".xls"})

ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        "text/csv",
        "application/csv",
        "text/plain",  # some OS/browsers send CSV as text/plain
        "application/vnd.ms-excel",  # .xls
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
        "application/octet-stream",  # generic binary — checked together with extension
    }
)

MAX_BYTES: int = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024  # 100 MB

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sanitize_filename(name: str) -> str:
    """
    Return a safe version of a filename.

    - Normalise unicode (NFC)
    - Strip directory separators and null bytes
    - Collapse whitespace to underscores
    - Allow only alphanumerics, underscores, hyphens, and dots
    - Truncate to 255 characters
    """
    name = unicodedata.normalize("NFC", name)
    name = os.path.basename(name)                      # strip any directory component
    name = name.replace("\x00", "")                    # strip null bytes
    name = re.sub(r"[\s]+", "_", name)                 # whitespace → underscore
    name = re.sub(r"[^\w.\-]", "", name, flags=re.ASCII)  # strip unsafe chars
    name = name[:255]                                  # hard length cap
    return name or "upload"


def _resolve_upload_dir() -> Path:
    """Return the absolute upload directory, creating it if necessary."""
    upload_path = Path(settings.UPLOAD_DIR)
    if not upload_path.is_absolute():
        # Resolve relative to the current working directory (the backend root)
        upload_path = Path.cwd() / upload_path
    upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path


def _validate_extension(filename: str) -> str:
    """
    Extract and validate the file extension.  Raises 400 on unsupported types.
    Returns the lower-cased extension (e.g. '.csv').
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            ),
        )
    return ext


def _validate_mime(mime_type: str | None, ext: str) -> str:
    """
    Validate the MIME type reported by the client.

    We deliberately do not rely solely on the client's content-type — we
    cross-check it against the file extension whitelist.
    """
    mime = (mime_type or "application/octet-stream").lower().split(";")[0].strip()
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported MIME type '{mime}'.",
        )
    return mime


async def _read_with_size_check(file: UploadFile) -> bytes:
    """
    Read the entire upload into memory while enforcing the size limit.
    Raises 413 if the file exceeds MAX_BYTES.
    """
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File exceeds the maximum allowed size of "
                f"{settings.MAX_UPLOAD_SIZE_MB} MB."
            ),
        )
    return content


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


async def save_upload(
    file: UploadFile,
    user_id: int,
    db: AsyncSession,
) -> Dataset:
    """
    Validate, store, and persist a dataset upload.

    Returns the newly created Dataset ORM object.
    """
    # 1. Validate extension (from the client filename — used for labelling only)
    raw_name: str = file.filename or "upload"
    ext = _validate_extension(raw_name)

    # 2. Validate MIME type
    mime = _validate_mime(file.content_type, ext)

    # 3. Read content with size cap
    content = await _read_with_size_check(file)
    file_size = len(content)

    # 4. Sanitise the original filename for safe DB storage
    sanitized_name = _sanitize_filename(raw_name)

    # 5. Generate a UUID-based stored filename — nothing from the user touches the path
    stored_uuid = uuid_module.uuid4()
    stored_filename = f"{stored_uuid}{ext}"

    # 6. Resolve destination path (never leaves UPLOAD_DIR)
    upload_dir = _resolve_upload_dir()
    dest_path = upload_dir / stored_filename

    # Safety check: confirm the resolved path is still inside upload_dir
    try:
        dest_path.resolve().relative_to(upload_dir.resolve())
    except ValueError:
        logger.error("Path traversal attempt detected: %s", stored_filename)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file path.",
        )

    # 7. Write to disk
    dest_path.write_bytes(content)
    logger.info(
        "Saved upload: user_id=%s, original=%s, stored=%s, size=%s bytes",
        user_id,
        sanitized_name,
        stored_filename,
        file_size,
    )

    # 8. Persist metadata in the database
    dataset = Dataset(
        uuid=stored_uuid,
        user_id=user_id,
        original_filename=sanitized_name,
        stored_filename=stored_filename,
        file_path=str(dest_path),
        file_size=file_size,
        mime_type=mime,
        extension=ext,
        status="uploaded",
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


async def list_datasets(
    user_id: int,
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[Dataset]]:
    """
    Return a paginated list of datasets owned by the user.

    Returns (total_count, items).
    """
    offset = (page - 1) * page_size

    count_stmt = select(func.count()).select_from(Dataset).where(Dataset.user_id == user_id)
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    items_stmt = (
        select(Dataset)
        .where(Dataset.user_id == user_id)
        .order_by(Dataset.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items_result = await db.execute(items_stmt)
    items = list(items_result.scalars().all())

    return total, items


async def get_dataset(
    dataset_uuid: UUID,
    user_id: int,
    db: AsyncSession,
) -> Dataset:
    """
    Fetch a single dataset by UUID while enforcing ownership.
    """
    stmt = (
        select(Dataset)
        .where(
            Dataset.uuid == dataset_uuid,
            Dataset.user_id == user_id,
        )
    )

    result = await db.execute(stmt)
    dataset = result.scalar_one_or_none()

    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found.",
        )

    return dataset


async def delete_dataset(
    dataset_uuid: UUID,
    user_id: int,
    db: AsyncSession,
) -> None:
    """
    Delete a dataset record and its physical file.
    """
    dataset = await get_dataset(
        dataset_uuid=dataset_uuid,
        user_id=user_id,
        db=db,
    )

    file_path = Path(dataset.file_path)

    if file_path.exists():
        file_path.unlink()
        logger.info("Deleted file: %s", file_path)
    else:
        logger.warning("File not found on disk during deletion: %s", file_path)

    await db.delete(dataset)
    await db.commit()

    logger.info(
        "Deleted dataset record: uuid=%s user_id=%s",
        dataset_uuid,
        user_id,
    )
